# services/text_to_speech/edge_tts_service.py
# Text-to-Speech using Microsoft Edge TTS (free, neural voices, multilingual)

import edge_tts
import asyncio
import time
import logging
import tempfile
import os
from typing import Optional
from config import LANGUAGE_VOICE_MAP

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Edge TTS-based Text-to-Speech.
    Supports English (Jenny), Hindi (Swara), Tamil (Pallavi).
    All voices are neural-quality and completely free.
    """

    def __init__(self):
        self.voice_map = LANGUAGE_VOICE_MAP
        logger.info("✅ Edge TTS initialized")

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        output_format: str = "audio-24khz-48kbitrate-mono-mp3",
    ) -> tuple[bytes, float]:
        """
        Convert text to speech audio bytes.

        Args:
            text: Text to convert
            language: Language code (en/hi/ta)
            output_format: Audio format

        Returns:
            Tuple of (audio_bytes, latency_ms)
        """
        start_time = time.time()

        voice = self.voice_map.get(language, self.voice_map["en"])

        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)

            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            audio_bytes = b"".join(audio_chunks)
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"🔊 TTS: '{text[:50]}...' | Voice: {voice} | "
                f"{len(audio_bytes)} bytes | {latency_ms:.1f}ms"
            )

            return audio_bytes, latency_ms

        except Exception as e:
            logger.error(f"TTS Error: {e}")
            return b"", (time.time() - start_time) * 1000

    async def synthesize_to_file(
        self, text: str, language: str = "en"
    ) -> tuple[str, float]:
        """
        Synthesize and save to temp file.
        Returns (file_path, latency_ms).
        """
        audio_bytes, latency_ms = await self.synthesize(text, language)

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        return tmp.name, latency_ms

    def synthesize_sync(self, text: str, language: str = "en") -> tuple[bytes, float]:
        """Synchronous wrapper for synthesize."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.synthesize(text, language))
        finally:
            loop.close()

    def get_available_voices(self) -> dict:
        """Return voice mapping."""
        return self.voice_map


# Singleton
_tts_instance = None


def get_tts_service() -> TextToSpeech:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
    return _tts_instance
