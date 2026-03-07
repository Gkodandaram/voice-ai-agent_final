# config.py - Central configuration for Voice AI Agent
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    groq_api_key: str = ""

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/voice_ai_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Session
    session_ttl_seconds: int = 3600

    # Whisper
    whisper_model: str = "base"

    # TTS Voices
    tts_voice_english: str = "en-US-JennyNeural"
    tts_voice_hindi: str = "hi-IN-SwaraNeural"
    tts_voice_tamil: str = "ta-IN-PallaviNeural"

    # Groq
    groq_model: str = "llama-3.1-70b-versatile"

    # Latency
    latency_target_ms: int = 450

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Language to TTS voice mapping
LANGUAGE_VOICE_MAP = {
    "en": settings.tts_voice_english,
    "hi": settings.tts_voice_hindi,
    "ta": settings.tts_voice_tamil,
}

# Supported languages
SUPPORTED_LANGUAGES = ["en", "hi", "ta"]

# Language display names
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
}
