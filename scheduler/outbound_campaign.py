# scheduler/outbound_campaign.py
# Outbound call campaign scheduler for reminders and follow-ups

import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Appointment, Patient, Doctor, AppointmentStatus
from services.text_to_speech.edge_tts_service import get_tts_service
from memory.session_memory.redis_memory import get_memory_service

logger = logging.getLogger(__name__)

tts_service = get_tts_service()
memory = get_memory_service()

scheduler = AsyncIOScheduler()


class OutboundCampaignManager:
    """
    Manages proactive outbound campaigns:
    - Appointment reminders (24h before)
    - Follow-up reminders
    - Vaccination reminders
    """

    def __init__(self):
        self.active_campaigns = {}

    async def send_appointment_reminder(self, appointment_id: str) -> dict:
        """
        Generate and queue reminder for an upcoming appointment.
        In production, this would trigger an actual outbound call.
        """
        db = SessionLocal()
        try:
            appointment = db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()

            if not appointment:
                return {"error": "Appointment not found"}

            patient = db.query(Patient).filter(
                Patient.id == appointment.patient_id
            ).first()

            doctor = db.query(Doctor).filter(
                Doctor.id == appointment.doctor_id
            ).first()

            if not (patient and doctor):
                return {"error": "Patient or doctor not found"}

            language = patient.preferred_language or "en"

            # Generate reminder message
            reminder_text = self._build_reminder_message(
                patient_name=patient.name,
                doctor_name=doctor.name,
                date=appointment.date,
                time=appointment.time,
                hospital=doctor.hospital,
                language=language,
            )

            # Generate audio
            audio_bytes, latency = await tts_service.synthesize(reminder_text, language)

            # Store in memory for retrieval
            campaign_id = f"reminder_{appointment_id}"
            memory.update_patient_memory(patient.id, {
                "last_reminder": {
                    "appointment_id": appointment_id,
                    "message": reminder_text,
                    "sent_at": datetime.now().isoformat(),
                }
            })

            logger.info(
                f"📞 Reminder generated for {patient.name}: "
                f"Dr. {doctor.name} on {appointment.date} at {appointment.time}"
            )

            return {
                "success": True,
                "campaign_id": campaign_id,
                "patient": patient.name,
                "message": reminder_text,
                "audio_size_bytes": len(audio_bytes),
                "language": language,
            }

        finally:
            db.close()

    def _build_reminder_message(
        self,
        patient_name: str,
        doctor_name: str,
        date: str,
        time: str,
        hospital: str,
        language: str,
    ) -> str:
        """Build reminder message in appropriate language."""
        if language == "hi":
            return (
                f"नमस्ते {patient_name} जी। यह 2Care.ai की तरफ से एक रिमाइंडर है। "
                f"आपकी {doctor_name} के साथ अपॉइंटमेंट {date} को {time} बजे है। "
                f"अस्पताल: {hospital}। "
                f"यदि आप अपॉइंटमेंट बदलना या रद्द करना चाहते हैं, तो बताएं।"
            )
        elif language == "ta":
            return (
                f"வணக்கம் {patient_name}. இது 2Care.ai இலிருந்து நினைவூட்டல். "
                f"உங்கள் {doctor_name} உடன் சந்திப்பு {date} அன்று {time} மணிக்கு. "
                f"மருத்துவமனை: {hospital}. "
                f"சந்திப்பை மாற்ற அல்லது ரத்து செய்ய விரும்பினால் தெரிவிக்கவும்."
            )
        else:
            return (
                f"Hello {patient_name}, this is a reminder from 2Care.ai. "
                f"You have an appointment with {doctor_name} on {date} at {time}. "
                f"Hospital: {hospital}. "
                f"If you'd like to reschedule or cancel, please let us know."
            )

    async def check_upcoming_appointments(self) -> list:
        """
        Find appointments in the next 24 hours and send reminders.
        Called by the scheduler.
        """
        db = SessionLocal()
        reminders_sent = []

        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            appointments = db.query(Appointment).filter(
                Appointment.date == tomorrow,
                Appointment.status == AppointmentStatus.SCHEDULED,
            ).all()

            logger.info(f"📅 Found {len(appointments)} appointments for {tomorrow}")

            for appointment in appointments:
                result = await self.send_appointment_reminder(appointment.id)
                reminders_sent.append(result)

            return reminders_sent

        finally:
            db.close()

    async def send_followup_campaign(self, days_after: int = 7) -> list:
        """
        Send follow-up messages to patients after their appointments.
        """
        db = SessionLocal()
        followups = []

        try:
            past_date = (datetime.now() - timedelta(days=days_after)).strftime("%Y-%m-%d")

            appointments = db.query(Appointment).filter(
                Appointment.date == past_date,
                Appointment.status == AppointmentStatus.COMPLETED,
            ).all()

            for appointment in appointments:
                patient = db.query(Patient).filter(
                    Patient.id == appointment.patient_id
                ).first()
                doctor = db.query(Doctor).filter(
                    Doctor.id == appointment.doctor_id
                ).first()

                if not (patient and doctor):
                    continue

                language = patient.preferred_language or "en"
                message = self._build_followup_message(
                    patient.name, doctor.name, language
                )

                audio_bytes, _ = await tts_service.synthesize(message, language)

                followups.append({
                    "patient": patient.name,
                    "message": message,
                    "language": language,
                })

            return followups

        finally:
            db.close()

    def _build_followup_message(
        self, patient_name: str, doctor_name: str, language: str
    ) -> str:
        if language == "hi":
            return (
                f"नमस्ते {patient_name} जी। {doctor_name} के साथ आपकी अपॉइंटमेंट के "
                f"बाद से एक हफ्ता हो गया है। क्या आप ठीक हैं? "
                f"क्या आपको फॉलो-अप अपॉइंटमेंट चाहिए?"
            )
        elif language == "ta":
            return (
                f"வணக்கம் {patient_name}. {doctor_name} உடன் உங்கள் சந்திப்புக்கு "
                f"ஒரு வாரம் ஆகிவிட்டது. நீங்கள் நலமாக இருக்கிறீர்களா? "
                f"மீண்டும் சந்திப்பு தேவையா?"
            )
        else:
            return (
                f"Hello {patient_name}. It's been a week since your appointment with "
                f"{doctor_name}. How are you feeling? "
                f"Would you like to schedule a follow-up appointment?"
            )


# ==========================================
# SCHEDULER SETUP
# ==========================================

campaign_manager = OutboundCampaignManager()


def setup_scheduler():
    """Configure and start the APScheduler."""

    # Run reminder checks daily at 9 AM
    scheduler.add_job(
        campaign_manager.check_upcoming_appointments,
        CronTrigger(hour=9, minute=0),
        id="daily_reminders",
        name="Daily Appointment Reminders",
        replace_existing=True,
    )

    # Run follow-up checks daily at 10 AM
    scheduler.add_job(
        campaign_manager.send_followup_campaign,
        CronTrigger(hour=10, minute=0),
        id="weekly_followups",
        name="Weekly Follow-up Campaign",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✅ Outbound campaign scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Scheduler stopped")
