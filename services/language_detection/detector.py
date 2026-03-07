# services/language_detection/detector.py
# Language detection using langdetect + Whisper's built-in detection

import logging
import time
from typing import Tuple

logger = logging.getLogger(__name__)

# Language code normalization map
# Whisper uses ISO 639-1 codes, we normalize to our 3 supported langs
LANGUAGE_MAP = {
    # English variants
    "en": "en",
    # Hindi
    "hi": "hi",
    # Tamil
    "ta": "ta",
    # Fallback for related languages
    "ur": "hi",   # Urdu → Hindi fallback
    "te": "ta",   # Telugu → Tamil fallback (closest supported)
    "ml": "ta",   # Malayalam → Tamil fallback
}

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
}

DEFAULT_LANGUAGE = "en"


class LanguageDetector:
    """
    Detects language from text.
    Primary: Uses Whisper's built-in language detection (most accurate).
    Fallback: Uses langdetect library.
    """

    def detect_from_whisper(self, whisper_language: str) -> Tuple[str, float]:
        """
        Normalize Whisper's detected language to our supported set.

        Args:
            whisper_language: Language code from Whisper

        Returns:
            Tuple of (normalized_language_code, confidence)
        """
        start = time.time()

        normalized = LANGUAGE_MAP.get(whisper_language, DEFAULT_LANGUAGE)
        confidence = 0.95 if whisper_language in LANGUAGE_MAP else 0.5

        latency_ms = (time.time() - start) * 1000
        logger.info(
            f"🌐 Language: {whisper_language} → {normalized} "
            f"({LANGUAGE_NAMES.get(normalized, 'Unknown')}) | {latency_ms:.1f}ms"
        )

        return normalized, confidence

    def detect_from_text(self, text: str) -> Tuple[str, float]:
        """
        Detect language from text using langdetect library.

        Args:
            text: Input text

        Returns:
            Tuple of (language_code, confidence)
        """
        start = time.time()

        if not text or len(text.strip()) < 3:
            return DEFAULT_LANGUAGE, 0.5

        try:
            from langdetect import detect_langs
            results = detect_langs(text)

            if results:
                top = results[0]
                lang_code = top.lang
                confidence = top.prob
                normalized = LANGUAGE_MAP.get(lang_code, DEFAULT_LANGUAGE)

                latency_ms = (time.time() - start) * 1000
                logger.info(
                    f"🌐 Text Lang Detection: {lang_code} → {normalized} "
                    f"(conf: {confidence:.2f}) | {latency_ms:.1f}ms"
                )
                return normalized, confidence

        except Exception as e:
            logger.warning(f"langdetect failed: {e}, using default")

        return DEFAULT_LANGUAGE, 0.5

    def detect(self, text: str, whisper_lang: str = None) -> Tuple[str, float]:
        """
        Best-effort language detection combining both methods.

        Args:
            text: Transcribed text
            whisper_lang: Language hint from Whisper (optional)

        Returns:
            Tuple of (language_code, confidence)
        """
        # If Whisper provided a language and it's supported, trust it
        if whisper_lang and whisper_lang in LANGUAGE_MAP:
            return self.detect_from_whisper(whisper_lang)

        # Fallback to text-based detection
        return self.detect_from_text(text)

    def get_language_name(self, code: str) -> str:
        return LANGUAGE_NAMES.get(code, "English")


# Singleton
_detector = None


def get_language_detector() -> LanguageDetector:
    global _detector
    if _detector is None:
        _detector = LanguageDetector()
    return _detector
