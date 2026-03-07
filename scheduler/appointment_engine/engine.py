# scheduler/appointment_engine/engine.py
# Core appointment scheduling logic - booking, cancellation, rescheduling

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from backend.models import Appointment, Doctor, DoctorSchedule, Patient, AppointmentStatus

logger = logging.getLogger(__name__)


class AppointmentEngine:
    """
    Core appointment management engine.
    Handles: booking, cancellation, rescheduling, availability checks.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # CHECK AVAILABILITY
    # ==========================================

    def get_available_slots(
        self, doctor_id: str, date: str
    ) -> dict:
        """
        Get available time slots for a doctor on a given date.

        Args:
            doctor_id: Doctor UUID
            date: Date string (YYYY-MM-DD)

        Returns:
            Dict with available_slots list and doctor info
        """
        doctor = self.db.query(Doctor).filter(
            Doctor.id == doctor_id, Doctor.is_active == True
        ).first()

        if not doctor:
            return {"error": "Doctor not found", "available_slots": []}

        schedule = self.db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.date == date,
            DoctorSchedule.is_active == True,
        ).first()

        if not schedule:
            return {
                "doctor": doctor.name,
                "date": date,
                "available_slots": [],
                "message": "No schedule found for this date",
            }

        all_slots = json.loads(schedule.available_slots)

        # Get booked slots for this doctor on this date
        booked = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == date,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).all()

        booked_times = {a.time for a in booked}

        # Filter out past times if date is today
        available = []
        now = datetime.now()
        for slot in all_slots:
            if slot in booked_times:
                continue
            if date == now.strftime("%Y-%m-%d"):
                slot_dt = datetime.strptime(f"{date} {slot}", "%Y-%m-%d %H:%M")
                if slot_dt <= now:
                    continue
            available.append(slot)

        return {
            "doctor": doctor.name,
            "specialization": doctor.specialization,
            "hospital": doctor.hospital,
            "date": date,
            "available_slots": available,
        }

    def find_doctor_by_specialization(self, specialization: str) -> list:
        """Find doctors by specialization (fuzzy match)."""
        spec_lower = specialization.lower()
        doctors = self.db.query(Doctor).filter(Doctor.is_active == True).all()
        matches = [
            d for d in doctors
            if spec_lower in d.specialization.lower()
            or d.specialization.lower() in spec_lower
        ]
        return matches

    def find_doctor_by_name(self, name: str) -> Optional[Doctor]:
        """Find doctor by name (partial match)."""
        name_lower = name.lower()
        doctors = self.db.query(Doctor).filter(Doctor.is_active == True).all()
        for d in doctors:
            if name_lower in d.name.lower():
                return d
        return None

    # ==========================================
    # BOOK APPOINTMENT
    # ==========================================

    def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        date: str,
        time: str,
        notes: str = "",
    ) -> dict:
        """
        Book an appointment after validating all constraints.

        Returns:
            Dict with success status and appointment details or error
        """
        # Validate doctor exists
        doctor = self.db.query(Doctor).filter(
            Doctor.id == doctor_id, Doctor.is_active == True
        ).first()
        if not doctor:
            return {"success": False, "error": "Doctor not found"}

        # Validate patient exists
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"success": False, "error": "Patient not found"}

        # Check if slot is in the past
        try:
            slot_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            if slot_dt < datetime.now():
                return {"success": False, "error": "Cannot book an appointment in the past"}
        except ValueError:
            return {"success": False, "error": "Invalid date or time format"}

        # Check for double booking (same patient, same time)
        existing = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.date == date,
            Appointment.time == time,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).first()
        if existing:
            return {"success": False, "error": "You already have an appointment at this time"}

        # Check if doctor slot is available
        doctor_booked = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == date,
            Appointment.time == time,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).first()
        if doctor_booked:
            available = self.get_available_slots(doctor_id, date)
            slots = available.get("available_slots", [])
            return {
                "success": False,
                "error": f"This slot is already booked",
                "alternative_slots": slots[:3],
            }

        # Create appointment
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            date=date,
            time=time,
            status=AppointmentStatus.SCHEDULED,
            notes=notes,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        logger.info(f"✅ Appointment booked: {appointment.id}")

        return {
            "success": True,
            "appointment_id": appointment.id,
            "patient": patient.name,
            "doctor": doctor.name,
            "specialization": doctor.specialization,
            "hospital": doctor.hospital,
            "date": date,
            "time": time,
            "status": "scheduled",
        }

    # ==========================================
    # CANCEL APPOINTMENT
    # ==========================================

    def cancel_appointment(
        self, appointment_id: str, patient_id: str
    ) -> dict:
        """Cancel an existing appointment."""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).first()

        if not appointment:
            return {"success": False, "error": "Appointment not found or already cancelled"}

        appointment.status = AppointmentStatus.CANCELLED
        self.db.commit()

        logger.info(f"🗑️ Appointment cancelled: {appointment_id}")

        return {
            "success": True,
            "message": f"Appointment on {appointment.date} at {appointment.time} has been cancelled",
            "appointment_id": appointment_id,
        }

    def cancel_latest_appointment(self, patient_id: str) -> dict:
        """Cancel the most recent upcoming appointment for a patient."""
        appointment = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).order_by(Appointment.date, Appointment.time).first()

        if not appointment:
            return {"success": False, "error": "No upcoming appointments found"}

        return self.cancel_appointment(appointment.id, patient_id)

    # ==========================================
    # RESCHEDULE APPOINTMENT
    # ==========================================

    def reschedule_appointment(
        self,
        appointment_id: str,
        patient_id: str,
        new_date: str,
        new_time: str,
    ) -> dict:
        """Reschedule an existing appointment to a new time."""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).first()

        if not appointment:
            return {"success": False, "error": "Appointment not found"}

        # Check new slot availability
        doctor_booked = self.db.query(Appointment).filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.date == new_date,
            Appointment.time == new_time,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.id != appointment_id,
        ).first()

        if doctor_booked:
            available = self.get_available_slots(appointment.doctor_id, new_date)
            return {
                "success": False,
                "error": "New slot is not available",
                "alternative_slots": available.get("available_slots", [])[:3],
            }

        old_date = appointment.date
        old_time = appointment.time

        appointment.date = new_date
        appointment.time = new_time
        appointment.status = AppointmentStatus.RESCHEDULED
        self.db.commit()

        doctor = self.db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()

        logger.info(f"🔄 Appointment rescheduled: {appointment_id}")

        return {
            "success": True,
            "appointment_id": appointment_id,
            "doctor": doctor.name if doctor else "Doctor",
            "old_date": old_date,
            "old_time": old_time,
            "new_date": new_date,
            "new_time": new_time,
        }

    # ==========================================
    # GET APPOINTMENTS
    # ==========================================

    def get_patient_appointments(self, patient_id: str) -> list:
        """Get all upcoming appointments for a patient."""
        appointments = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
        ).order_by(Appointment.date, Appointment.time).all()

        result = []
        for appt in appointments:
            doctor = self.db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
            result.append({
                "appointment_id": appt.id,
                "doctor": doctor.name if doctor else "Unknown",
                "specialization": doctor.specialization if doctor else "Unknown",
                "hospital": doctor.hospital if doctor else "Unknown",
                "date": appt.date,
                "time": appt.time,
                "status": appt.status.value,
            })

        return result

    def resolve_date(self, date_str: str) -> str:
        """
        Convert relative date strings to YYYY-MM-DD format.
        Examples: 'tomorrow', 'today', 'monday', '2024-01-15'
        """
        date_str = date_str.lower().strip()
        today = datetime.now()

        if date_str in ("today", "aaj", "இன்று"):
            return today.strftime("%Y-%m-%d")
        elif date_str in ("tomorrow", "kal", "நாளை"):
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str in ("day after tomorrow", "परसों"):
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")

        # Handle day names
        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        if date_str in days:
            target = days[date_str]
            current = today.weekday()
            delta = (target - current) % 7 or 7
            return (today + timedelta(days=delta)).strftime("%Y-%m-%d")

        # Try parsing as-is
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Default to tomorrow
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
