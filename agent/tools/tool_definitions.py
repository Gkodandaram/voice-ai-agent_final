# agent/tools/tool_definitions.py
# Tool definitions for LLM function calling + tool executor

import logging
from typing import Any
from scheduler.appointment_engine.engine import AppointmentEngine

logger = logging.getLogger(__name__)

# ==========================================
# TOOL DEFINITIONS (for Groq function calling)
# ==========================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "checkAvailability",
            "description": "Check available appointment slots for a doctor on a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialization": {
                        "type": "string",
                        "description": "Doctor's specialization (e.g., 'cardiologist', 'dermatologist')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check (e.g., 'tomorrow', '2024-01-15', 'monday')",
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "Specific doctor name if requested",
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bookAppointment",
            "description": "Book an appointment for the patient with a doctor",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "Doctor's ID from availability check",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date (YYYY-MM-DD or relative like 'tomorrow')",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time (HH:MM format, e.g., '10:00')",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes for the appointment",
                    },
                },
                "required": ["doctor_id", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelAppointment",
            "description": "Cancel an existing appointment for the patient",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID of the appointment to cancel (optional - cancels latest if not provided)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rescheduleAppointment",
            "description": "Reschedule an existing appointment to a new date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID of appointment to reschedule",
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New date for the appointment",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New time for the appointment (HH:MM)",
                    },
                },
                "required": ["new_date", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getPatientAppointments",
            "description": "Get all upcoming appointments for the current patient",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ==========================================
# TOOL EXECUTOR
# ==========================================

def execute_tool(tool_name: str, args: dict) -> dict:
    """
    Execute a tool call from the LLM.

    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments including patient_id and db_session

    Returns:
        Tool result dict
    """
    patient_id = args.pop("patient_id", None)
    db_session = args.pop("db_session", None)

    if not db_session:
        return {"error": "Database session not available"}

    engine = AppointmentEngine(db=db_session)

    try:
        if tool_name == "checkAvailability":
            return _check_availability(engine, args)

        elif tool_name == "bookAppointment":
            return _book_appointment(engine, patient_id, args)

        elif tool_name == "cancelAppointment":
            return _cancel_appointment(engine, patient_id, args)

        elif tool_name == "rescheduleAppointment":
            return _reschedule_appointment(engine, patient_id, args)

        elif tool_name == "getPatientAppointments":
            appointments = engine.get_patient_appointments(patient_id)
            return {"appointments": appointments, "count": len(appointments)}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return {"error": str(e)}


def _check_availability(engine: AppointmentEngine, args: dict) -> dict:
    """Find doctors and check their availability."""
    date_str = args.get("date", "tomorrow")
    specialization = args.get("specialization", "")
    doctor_name = args.get("doctor_name", "")

    # Resolve date
    date = engine.resolve_date(date_str)

    # Find doctor(s)
    doctors = []
    if doctor_name:
        doc = engine.find_doctor_by_name(doctor_name)
        if doc:
            doctors = [doc]
    if not doctors and specialization:
        doctors = engine.find_doctor_by_specialization(specialization)

    if not doctors:
        # Return all doctors if no specific filter
        from backend.models import Doctor
        doctors = engine.db.query(Doctor).filter(Doctor.is_active == True).all()[:3]

    results = []
    for doc in doctors[:3]:  # Limit to 3 doctors
        availability = engine.get_available_slots(doc.id, date)
        results.append({
            "doctor_id": doc.id,
            "doctor_name": doc.name,
            "specialization": doc.specialization,
            "hospital": doc.hospital,
            "date": date,
            "available_slots": availability.get("available_slots", [])[:5],
        })

    return {"date": date, "doctors": results}


def _book_appointment(engine: AppointmentEngine, patient_id: str, args: dict) -> dict:
    """Book appointment with date resolution."""
    date_str = args.get("date", "tomorrow")
    date = engine.resolve_date(date_str)

    return engine.book_appointment(
        patient_id=patient_id,
        doctor_id=args["doctor_id"],
        date=date,
        time=args["time"],
        notes=args.get("notes", ""),
    )


def _cancel_appointment(engine: AppointmentEngine, patient_id: str, args: dict) -> dict:
    """Cancel appointment."""
    appointment_id = args.get("appointment_id")

    if appointment_id:
        return engine.cancel_appointment(appointment_id, patient_id)
    else:
        return engine.cancel_latest_appointment(patient_id)


def _reschedule_appointment(engine: AppointmentEngine, patient_id: str, args: dict) -> dict:
    """Reschedule appointment."""
    appointment_id = args.get("appointment_id")
    new_date = engine.resolve_date(args.get("new_date", "tomorrow"))
    new_time = args.get("new_time")

    if not appointment_id:
        # Get latest appointment
        appointments = engine.get_patient_appointments(patient_id)
        if not appointments:
            return {"error": "No appointments found to reschedule"}
        appointment_id = appointments[0]["appointment_id"]

    return engine.reschedule_appointment(
        appointment_id=appointment_id,
        patient_id=patient_id,
        new_date=new_date,
        new_time=new_time,
    )
