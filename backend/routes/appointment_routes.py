# backend/routes/appointment_routes.py
# REST API endpoints for appointment management

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.database import get_db_session
from scheduler.appointment_engine.engine import AppointmentEngine
from backend.models import Doctor, Patient

router = APIRouter(prefix="/api", tags=["appointments"])


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class BookAppointmentRequest(BaseModel):
    patient_id: str
    doctor_id: str
    date: str
    time: str
    notes: Optional[str] = ""


class CancelAppointmentRequest(BaseModel):
    appointment_id: str
    patient_id: str


class RescheduleAppointmentRequest(BaseModel):
    appointment_id: str
    patient_id: str
    new_date: str
    new_time: str


# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/health")
def health_check():
    return {"status": "running", "service": "2Care.ai Voice AI Agent"}


@router.get("/doctors")
def get_doctors(db: Session = Depends(get_db_session)):
    """Get all available doctors."""
    doctors = db.query(Doctor).filter(Doctor.is_active == True).all()
    return {
        "doctors": [
            {
                "id": d.id,
                "name": d.name,
                "specialization": d.specialization,
                "hospital": d.hospital,
            }
            for d in doctors
        ]
    }


@router.get("/availability/{doctor_id}/{date}")
def check_availability(
    doctor_id: str,
    date: str,
    db: Session = Depends(get_db_session),
):
    """Check doctor availability for a given date."""
    engine = AppointmentEngine(db)
    return engine.get_available_slots(doctor_id, date)


@router.post("/appointments/book")
def book_appointment(
    request: BookAppointmentRequest,
    db: Session = Depends(get_db_session),
):
    """Book a new appointment."""
    engine = AppointmentEngine(db)
    result = engine.book_appointment(
        patient_id=request.patient_id,
        doctor_id=request.doctor_id,
        date=request.date,
        time=request.time,
        notes=request.notes,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/appointments/cancel")
def cancel_appointment(
    request: CancelAppointmentRequest,
    db: Session = Depends(get_db_session),
):
    """Cancel an appointment."""
    engine = AppointmentEngine(db)
    result = engine.cancel_appointment(request.appointment_id, request.patient_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/appointments/reschedule")
def reschedule_appointment(
    request: RescheduleAppointmentRequest,
    db: Session = Depends(get_db_session),
):
    """Reschedule an appointment."""
    engine = AppointmentEngine(db)
    result = engine.reschedule_appointment(
        appointment_id=request.appointment_id,
        patient_id=request.patient_id,
        new_date=request.new_date,
        new_time=request.new_time,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/appointments/{patient_id}")
def get_patient_appointments(
    patient_id: str,
    db: Session = Depends(get_db_session),
):
    """Get all appointments for a patient."""
    engine = AppointmentEngine(db)
    appointments = engine.get_patient_appointments(patient_id)
    return {"patient_id": patient_id, "appointments": appointments}


@router.get("/patients")
def get_patients(db: Session = Depends(get_db_session)):
    """Get all patients (for testing)."""
    patients = db.query(Patient).all()
    return {
        "patients": [
            {
                "id": p.id,
                "name": p.name,
                "phone": p.phone,
                "preferred_language": p.preferred_language,
            }
            for p in patients
        ]
    }
