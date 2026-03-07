# backend/database.py - Database connection and session management
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from backend.models import Base
from config import settings
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

import os
db_url = settings.database_url
if "postgresql" in db_url:
    db_url = "sqlite:///./voice_ai.db"

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables and seed sample data."""
    Base.metadata.create_all(bind=engine)
    seed_sample_data()
    logger.info("✅ Database initialized successfully")


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def get_db_session():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_sample_data():
    """Seed database with sample doctors and patients."""
    from backend.models import Doctor, DoctorSchedule, Patient
    
    with get_db() as db:
        # Skip if data already exists
        if db.query(Doctor).count() > 0:
            return

        # Sample doctors
        doctors = [
            Doctor(
                id="doc-001",
                name="Dr. Rajesh Sharma",
                specialization="Cardiologist",
                hospital="Apollo Hospital",
                phone="+91-9876543210",
            ),
            Doctor(
                id="doc-002",
                name="Dr. Priya Menon",
                specialization="Dermatologist",
                hospital="Fortis Hospital",
                phone="+91-9876543211",
            ),
            Doctor(
                id="doc-003",
                name="Dr. Arun Kumar",
                specialization="General Physician",
                hospital="Apollo Hospital",
                phone="+91-9876543212",
            ),
            Doctor(
                id="doc-004",
                name="Dr. Kavitha Rajan",
                specialization="Neurologist",
                hospital="MIOT Hospital",
                phone="+91-9876543213",
            ),
            Doctor(
                id="doc-005",
                name="Dr. Suresh Iyer",
                specialization="Orthopedic",
                hospital="Fortis Hospital",
                phone="+91-9876543214",
            ),
        ]
        db.add_all(doctors)
        db.flush()

        # Generate schedule for next 7 days
        base_slots = ["09:00", "09:30", "10:00", "10:30", "11:00",
                      "14:00", "14:30", "15:00", "15:30", "16:00"]
        
        for doctor in doctors:
            for day_offset in range(7):
                date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                schedule = DoctorSchedule(
                    doctor_id=doctor.id,
                    date=date,
                    available_slots=json.dumps(base_slots),
                )
                db.add(schedule)

        # Sample patients
        patients = [
            Patient(
                id="pat-001",
                name="Ravi Kumar",
                phone="+91-9000000001",
                preferred_language="en",
                preferred_doctor="Dr. Rajesh Sharma",
                preferred_hospital="Apollo Hospital",
            ),
            Patient(
                id="pat-002",
                name="Anita Singh",
                phone="+91-9000000002",
                preferred_language="hi",
            ),
            Patient(
                id="pat-003",
                name="Murugan Selvam",
                phone="+91-9000000003",
                preferred_language="ta",
            ),
        ]
        db.add_all(patients)
        logger.info("✅ Sample data seeded successfully")
