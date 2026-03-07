# services/speech_to_text/whisper_stt.py
# Speech-to-Text using OpenAI Whisper (runs locally, completely free)

import whisper
import numpy as np
import time
import logging
import tempfile
import os
import soundfile as sf
from typing import Tuple

logger = logging.getLogger(__name__)

# Global model instance (loaded once)
_model = None


def load_whisper_model(model_size: str = "base") -> whisper.Whisper:
    """Load Whisper model once and reuse."""
    global _model
    if _model is None:
        logger.info(f"🔄 Loading Whisper model: {model_size}")
        _model = whisper.load_model(model_size)
        logger.info(f"✅ Whisper model '{model_size}' loaded")
    return _model


class SpeechToText:
    """
    Whisper-based Speech-to-Text.
    Supports English, Hindi, Tamil (and 99 more languages).
    """

    def __init__(self, model_size: str = "base"):
        self.model = load_whisper_model(model_size)
        self.model_size = model_size

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> Tuple[str, str, float]:
        """
        Transcribe raw audio bytes.

        Args:
            audio_bytes: Raw PCM audio bytes
            sample_rate: Audio sample rate (default 16000 Hz)

        Returns:
            Tuple of (transcribed_text, detected_language, latency_ms)
        """
        start_time = time.time()

        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]

            # Resample if needed (Whisper expects 16kHz)
            if sample_rate != 16000:
                audio_array = self._resample(audio_array, sample_rate, 16000)

            # Transcribe
            result = self.model.transcribe(
                audio_array,
                fp16=False,
                language=None,         # Auto-detect language
                task="transcribe",
                verbose=False,
            )

            text = result["text"].strip()
            language = result.get("language", "en")

            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"🎙️ STT: '{text}' | Lang: {language} | {latency_ms:.1f}ms")

            return text, language, latency_ms

        except Exception as e:
            logger.error(f"STT Error: {e}")
            return "", "en", (time.time() - start_time) * 1000

    def transcribe_file(self, file_path: str) -> Tuple[str, str, float]:
        """
        Transcribe an audio file.

        Args:
            file_path: Path to audio file (wav, mp3, etc.)

        Returns:
            Tuple of (transcribed_text, detected_language, latency_ms)
        """
        start_time = time.time()

        try:
            result = self.model.transcribe(
                file_path,
                fp16=False,
                language=None,
                task="transcribe",
                verbose=False,
            )

            text = result["text"].strip()
            language = result.get("language", "en")

            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"🎙️ STT (file): '{text}' | Lang: {language} | {latency_ms:.1f}ms")

            return text, language, latency_ms

        except Exception as e:
            logger.error(f"STT File Error: {e}")
            return "", "en", (time.time() - start_time) * 1000

    def transcribe_webm(self, audio_bytes: bytes) -> Tuple[str, str, float]:
        """
        Transcribe WebM audio from browser WebSocket.
        Saves to temp file and processes.
        """
        start_time = time.time()

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            text, language, _ = self.transcribe_file(tmp_path)
            latency_ms = (time.time() - start_time) * 1000
            return text, language, latency_ms
        finally:
            os.unlink(tmp_path)

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple linear resampling."""
        ratio = target_sr / orig_sr
        new_length = int(len(audio) * ratio)
        return np.interp(
            np.linspace(0, len(audio) - 1, new_length),
            np.arange(len(audio)),
            audio,
        )


# Singleton instance
_stt_instance = None


def get_stt_service(model_size: str = "base") -> SpeechToText:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText(model_size)
    return _stt_instance
