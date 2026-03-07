# memory/session_memory/redis_memory.py
# Session and persistent memory using Redis

import redis
import json
import time
import logging
from typing import Optional, Any
from config import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Two-level memory system using Redis:
    1. Session Memory  - current conversation context (TTL: 1 hour)
    2. Persistent Memory - patient long-term preferences (TTL: 30 days)
    """

    def __init__(self):
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        self.session_ttl = settings.session_ttl_seconds
        self.persistent_ttl = 30 * 24 * 3600  # 30 days

        # Test connection
        try:
            self.client.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}. Using in-memory fallback.")
            self.client = None
            self._fallback_store = {}

    # ==========================================
    # SESSION MEMORY (Current conversation)
    # ==========================================

    def get_session(self, session_id: str) -> dict:
        """Get current conversation session."""
        key = f"session:{session_id}"
        return self._get(key) or self._default_session()

    def update_session(self, session_id: str, data: dict) -> None:
        """Update session with new conversation state."""
        key = f"session:{session_id}"
        existing = self.get_session(session_id)
        existing.update(data)
        existing["last_updated"] = time.time()
        self._set(key, existing, self.session_ttl)
        logger.debug(f"📝 Session updated: {session_id}")

    def add_message_to_session(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Add a message to conversation history."""
        session = self.get_session(session_id)
        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        # Keep only last 20 messages to avoid token overflow
        session["messages"] = session["messages"][-20:]
        self.update_session(session_id, session)

    def clear_session(self, session_id: str) -> None:
        """Clear session data."""
        key = f"session:{session_id}"
        self._delete(key)
        logger.info(f"🗑️ Session cleared: {session_id}")

    def get_conversation_history(self, session_id: str) -> list:
        """Get conversation messages for LLM context."""
        session = self.get_session(session_id)
        return session.get("messages", [])

    # ==========================================
    # PERSISTENT MEMORY (Patient long-term)
    # ==========================================

    def get_patient_memory(self, patient_id: str) -> dict:
        """Get patient's persistent preferences."""
        key = f"patient:{patient_id}"
        return self._get(key) or self._default_patient_memory()

    def update_patient_memory(self, patient_id: str, data: dict) -> None:
        """Update patient's persistent memory."""
        key = f"patient:{patient_id}"
        existing = self.get_patient_memory(patient_id)
        existing.update(data)
        existing["last_updated"] = time.time()
        self._set(key, existing, self.persistent_ttl)
        logger.info(f"💾 Patient memory updated: {patient_id}")

    def remember_appointment(self, patient_id: str, appointment: dict) -> None:
        """Store appointment in patient history."""
        memory = self.get_patient_memory(patient_id)
        memory["past_appointments"].append(appointment)
        memory["past_appointments"] = memory["past_appointments"][-10:]  # Keep last 10
        self.update_patient_memory(patient_id, memory)

    # ==========================================
    # LATENCY TRACKING
    # ==========================================

    def log_latency(self, session_id: str, stage: str, latency_ms: float) -> None:
        """Log latency metrics."""
        key = f"latency:{session_id}"
        data = self._get(key) or {}
        if stage not in data:
            data[stage] = []
        data[stage].append(round(latency_ms, 2))
        self._set(key, data, 3600)

    def get_latency_report(self, session_id: str) -> dict:
        """Get latency breakdown for a session."""
        key = f"latency:{session_id}"
        data = self._get(key) or {}
        report = {}
        for stage, values in data.items():
            if values:
                report[stage] = {
                    "avg_ms": round(sum(values) / len(values), 2),
                    "min_ms": round(min(values), 2),
                    "max_ms": round(max(values), 2),
                    "count": len(values),
                }
        return report

    # ==========================================
    # HELPERS
    # ==========================================

    def _get(self, key: str) -> Optional[Any]:
        try:
            if self.client:
                value = self.client.get(key)
                return json.loads(value) if value else None
            return self._fallback_store.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def _set(self, key: str, value: Any, ttl: int = None) -> None:
        try:
            serialized = json.dumps(value)
            if self.client:
                if ttl:
                    self.client.setex(key, ttl, serialized)
                else:
                    self.client.set(key, serialized)
            else:
                self._fallback_store[key] = value
        except Exception as e:
            logger.error(f"Redis SET error: {e}")

    def _delete(self, key: str) -> None:
        try:
            if self.client:
                self.client.delete(key)
            elif key in self._fallback_store:
                del self._fallback_store[key]
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")

    def _default_session(self) -> dict:
        return {
            "messages": [],
            "intent": None,
            "pending_data": {},
            "language": "en",
            "patient_id": None,
            "last_updated": time.time(),
        }

    def _default_patient_memory(self) -> dict:
        return {
            "preferred_language": "en",
            "preferred_doctor": None,
            "preferred_hospital": None,
            "past_appointments": [],
            "last_updated": time.time(),
        }


# Singleton
_memory_service = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
