"""Translation service - Fast, context-aware bidirectional translation."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class TranslationService:
    """Context-aware translation between source and target languages."""

    def __init__(self, api_key: str | None = None):
        """Initialize with Gemini API."""
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = "gemini-3.1-flash-lite-preview"

    def translate(self, text: str, source_lang: str, target_lang: str, user_level: str) -> str:
        """Translate text dynamically based on the detected input language.

        Args:
            text: Text to translate
            source_lang: The user's base language (e.g., "es")
            target_lang: The language being learned (e.g., "de")
            user_level: The user's proficiency level (e.g., "A2")

        Returns:
            Translated text
        """
        start_time = time.time()

        prompt = (
            f"You are a language tutor. The user's base language is {source_lang.upper()} "
            f"and they are learning {target_lang.upper()} at a {user_level} level.\n\n"
            f"Task: Detect the language of the provided text.\n"
            f"- If the text is in {source_lang.upper()}, translate it to {target_lang.upper()}.\n"
            f"- If the text is in {target_lang.upper()}, translate it to {source_lang.upper()}.\n\n"
            f"Ensure the translation is natural, colloquial, and strictly matches the {user_level} level.\n"
            f"Return ONLY the translation string, with no quotation marks or explanations.\n\n"
            f"Text: {text}"
        )

        try:
            logger.debug(
                "translate start source=%s target=%s level=%s text_length=%s",
                source_lang,
                target_lang,
                user_level,
                len(text),
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=200,
                ),
            )

            translation = response.text.strip()
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                "translate success duration_ms=%.2f output_length=%s",
                duration_ms,
                len(translation),
            )

            return translation

        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "translate failed duration_ms=%.2f error=%s",
                duration_ms,
                str(err),
            )
            raise RuntimeError(f"Translation failed: {err}") from err