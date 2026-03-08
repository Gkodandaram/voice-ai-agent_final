# services/speech_to_text/whisper_stt.py
# STT Service - Groq Whisper API based (cloud, no local model needed)

import logging
import time
from typing import Tuple

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Cloud-based Speech-to-Text using Groq Whisper API.
    """

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        logger.info("✅ STT Service initialized")

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> Tuple[str, str, float]:
        start_time = time.time()
        try:
            from groq import Groq
            import tempfile, os
            client = Groq()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=("audio.wav", f),
                    model="whisper-large-v3",
                )
            os.unlink(tmp_path)
            text = result.text.strip()
            latency_ms = (time.time() - start_time) * 1000
            return text, "en", latency_ms
        except Exception as e:
            logger.error(f"STT Error: {e}")
            return "", "en", (time.time() - start_time) * 1000

    def transcribe_file(self, file_path: str) -> Tuple[str, str, float]:
        start_time = time.time()
        try:
            from groq import Groq
            client = Groq()
            with open(file_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=(file_path, f),
                    model="whisper-large-v3",
                )
            text = result.text.strip()
            latency_ms = (time.time() - start_time) * 1000
            return text, "en", latency_ms
        except Exception as e:
            logger.error(f"STT File Error: {e}")
            return "", "en", (time.time() - start_time) * 1000

    def transcribe_webm(self, audio_bytes: bytes) -> Tuple[str, str, float]:
        return self.transcribe_bytes(audio_bytes)


_stt_instance = None


def get_stt_service(model_size: str = "base") -> SpeechToText:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText(model_size)
    return _stt_instance