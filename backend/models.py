# backend/models.py - SQLAlchemy Database Models
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    RESCHEDULED = "rescheduled"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), nullable=True)
    preferred_language = Column(String(10), default="en")
    preferred_doctor = Column(String(255), nullable=True)
    preferred_hospital = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    specialization = Column(String(255), nullable=False)
    hospital = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    schedules = relationship("DoctorSchedule", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(String, primary_key=True, default=generate_uuid)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    date = Column(String(20), nullable=False)  # YYYY-MM-DD
    available_slots = Column(Text, nullable=False)  # JSON array of time slots
    is_active = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="schedules")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=generate_uuid)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    date = Column(String(20), nullable=False)       # YYYY-MM-DD
    time = Column(String(10), nullable=False)       # HH:MM
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, nullable=False)
    patient_id = Column(String, nullable=True)
    direction = Column(String(20), default="inbound")  # inbound / outbound
    language_detected = Column(String(10), nullable=True)
    transcript = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    avg_latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
