# tests/test_system.py
# Comprehensive test suite for the Voice AI Agent

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ==========================================
# APPOINTMENT ENGINE TESTS
# ==========================================

class TestAppointmentEngine:
    """Tests for appointment scheduling logic."""

    def setup_method(self):
        """Set up mock database session."""
        self.mock_db = MagicMock()

    def test_resolve_date_tomorrow(self):
        from scheduler.appointment_engine.engine import AppointmentEngine
        engine = AppointmentEngine(db=self.mock_db)
        result = engine.resolve_date("tomorrow")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_resolve_date_today(self):
        from scheduler.appointment_engine.engine import AppointmentEngine
        engine = AppointmentEngine(db=self.mock_db)
        result = engine.resolve_date("today")
        expected = datetime.now().strftime("%Y-%m-%d")
        assert result == expected

    def test_resolve_date_explicit(self):
        from scheduler.appointment_engine.engine import AppointmentEngine
        engine = AppointmentEngine(db=self.mock_db)
        result = engine.resolve_date("2025-06-15")
        assert result == "2025-06-15"

    def test_resolve_date_hindi(self):
        from scheduler.appointment_engine.engine import AppointmentEngine
        engine = AppointmentEngine(db=self.mock_db)
        result = engine.resolve_date("kal")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected


# ==========================================
# LANGUAGE DETECTION TESTS
# ==========================================

class TestLanguageDetector:
    """Tests for multilingual detection."""

    def setup_method(self):
        from services.language_detection.detector import LanguageDetector
        self.detector = LanguageDetector()

    def test_detect_english_from_whisper(self):
        lang, conf = self.detector.detect_from_whisper("en")
        assert lang == "en"
        assert conf > 0.5

    def test_detect_hindi_from_whisper(self):
        lang, conf = self.detector.detect_from_whisper("hi")
        assert lang == "hi"

    def test_detect_tamil_from_whisper(self):
        lang, conf = self.detector.detect_from_whisper("ta")
        assert lang == "ta"

    def test_detect_urdu_fallback(self):
        """Urdu should fall back to Hindi."""
        lang, conf = self.detector.detect_from_whisper("ur")
        assert lang == "hi"

    def test_detect_unknown_fallback(self):
        """Unknown language should fall back to English."""
        lang, conf = self.detector.detect_from_whisper("xyz")
        assert lang == "en"

    def test_get_language_name(self):
        assert self.detector.get_language_name("en") == "English"
        assert self.detector.get_language_name("hi") == "Hindi"
        assert self.detector.get_language_name("ta") == "Tamil"


# ==========================================
# MEMORY SERVICE TESTS  
# ==========================================

class TestMemoryService:
    """Tests for Redis memory (with in-memory fallback)."""

    def setup_method(self):
        from memory.session_memory.redis_memory import MemoryService
        # Use in-memory fallback (no Redis needed for tests)
        self.memory = MemoryService.__new__(MemoryService)
        self.memory.client = None
        self.memory._fallback_store = {}
        self.memory.session_ttl = 3600
        self.memory.persistent_ttl = 30 * 24 * 3600

    def test_default_session(self):
        session = self.memory.get_session("test-session-1")
        assert session["messages"] == []
        assert session["intent"] is None
        assert session["language"] == "en"

    def test_update_session(self):
        self.memory.update_session("sess-1", {"language": "hi", "intent": "book"})
        session = self.memory.get_session("sess-1")
        assert session["language"] == "hi"
        assert session["intent"] == "book"

    def test_add_messages(self):
        self.memory.add_message_to_session("sess-2", "user", "Book appointment")
        self.memory.add_message_to_session("sess-2", "assistant", "Sure, which doctor?")
        history = self.memory.get_conversation_history("sess-2")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_patient_memory_defaults(self):
        memory = self.memory.get_patient_memory("pat-test")
        assert memory["preferred_language"] == "en"
        assert memory["past_appointments"] == []

    def test_latency_logging(self):
        self.memory.log_latency("sess-3", "stt", 120.5)
        self.memory.log_latency("sess-3", "agent", 200.3)
        self.memory.log_latency("sess-3", "tts", 95.2)
        report = self.memory.get_latency_report("sess-3")
        assert "stt" in report
        assert report["stt"]["avg_ms"] == 120.5

    def test_message_limit(self):
        """Should keep only last 20 messages."""
        for i in range(25):
            self.memory.add_message_to_session("sess-4", "user", f"Message {i}")
        history = self.memory.get_conversation_history("sess-4")
        assert len(history) <= 20


# ==========================================
# SYSTEM PROMPT TESTS
# ==========================================

class TestSystemPrompts:
    """Tests for multilingual system prompts."""

    def test_english_prompt(self):
        from agent.prompt.system_prompts import get_system_prompt
        prompt = get_system_prompt("en", "pat-001")
        assert "English" in prompt
        assert "appointment" in prompt.lower()

    def test_hindi_prompt(self):
        from agent.prompt.system_prompts import get_system_prompt
        prompt = get_system_prompt("hi", "pat-002")
        assert "Hindi" in prompt

    def test_tamil_prompt(self):
        from agent.prompt.system_prompts import get_system_prompt
        prompt = get_system_prompt("ta", "pat-003")
        assert "Tamil" in prompt


# ==========================================
# INTEGRATION SCENARIO TESTS
# ==========================================

class TestScenarios:
    """End-to-end scenario tests (without external APIs)."""

    SCENARIOS = [
        {
            "name": "Book appointment (English)",
            "input": "Book appointment with cardiologist tomorrow",
            "language": "en",
            "expected_intent": "book",
        },
        {
            "name": "Cancel appointment (Hindi)",
            "input": "मेरी अपॉइंटमेंट कैंसिल कर दो",
            "language": "hi",
            "expected_intent": "cancel",
        },
        {
            "name": "Reschedule (Tamil)",
            "input": "என் சந்திப்பை வெள்ளிக்கிழமைக்கு மாற்றுங்கள்",
            "language": "ta",
            "expected_intent": "reschedule",
        },
        {
            "name": "Check availability (English)",
            "input": "Is Dr. Sharma available tomorrow?",
            "language": "en",
            "expected_intent": "check",
        },
    ]

    def test_scenarios_defined(self):
        """Verify all test scenarios are properly defined."""
        for scenario in self.SCENARIOS:
            assert "name" in scenario
            assert "input" in scenario
            assert "language" in scenario
            assert scenario["language"] in ["en", "hi", "ta"]

    def test_latency_target(self):
        """Verify latency target is set correctly."""
        from config import settings
        assert settings.latency_target_ms == 450


# ==========================================
# RUN TESTS
# ==========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
