"""LLM Generation service - Generate rich sentence recommendations based on context."""

from __future__ import annotations

import json
import logging
import time
import re
from typing import Any

from google import genai
from google.genai import types

from app.api.schemas import PracticeExercise, PracticeGenerateRequest

logger = logging.getLogger(__name__)


class LLMGenerationService:
    """Generate rich sentence recommendations using Gemini LLM."""

    def __init__(self, api_key: str | None = None):
        """Initialize with Gemini API."""
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = "gemini-3.1-flash-lite-preview"  # Using stable model

    def _clean_json_response(self, text: str) -> str:
        """Helper to cleanly strip markdown formatting from LLM JSON responses."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def generate_recommendations(
        self,
        original_text: str,
        translation: str,
        context_vocabulary: list[dict[str, Any]],
        user_level: str,
        target_lang: str,
        context_scenario: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Generate rich sentence recommendations using LLM."""
        start_time = time.time()

        # Build vocabulary context
        vocab_context = "\n".join(
            [
                f"- {v['word']} ({v.get('meaning', 'N/A')}): {v.get('category', 'general')}"
                for v in context_vocabulary[:10]
            ]
        )

        # Build situational context string dynamically
        scenario_lines = []
        if context_scenario:
            for key, value in context_scenario.items():
                if value:
                    scenario_lines.append(f"- {key.capitalize()}: {value}")

        scenario_text = "\n".join(scenario_lines) if scenario_lines else "- General daily conversation."

        prompt = f"""
You are an expert language tutor generating highly situational example sentences for a {user_level} level learner.

SITUATIONAL CONTEXT:
The user is currently in this specific scenario:
{scenario_text}

LINGUISTIC CONTEXT:
- Input text/word: "{original_text}"
- Translation: "{translation}"
- Available vocabulary:
{vocab_context}

TASK: Generate 5 natural, conversational sentences strictly in {target_lang.upper()} that:
1. Fit PERFECTLY within the specific Situational Context described above (e.g. if the location is a 'supermarket', provide phrases used at the cashier).
2. Are strictly appropriate for a {user_level} level learner.
3. Teach practical, real-world ways to express ideas related to the input text in this exact scenario.
4. Optionally use vocabulary from the list above if it fits naturally.

Return ONLY a JSON array of objects. Do not include markdown blocks. Example format:
[
  {{
    "sentence": "Ich möchte mit Karte zahlen, bitte.",
    "reason": "Standard phrase used when interacting with a cashier.",
    "usage": "Use this when the cashier tells you the total amount."
  }}
]
"""

        try:
            logger.debug(
                "generate_recommendations start level=%s lang=%s vocab_count=%s scenario=%s",
                user_level,
                target_lang,
                len(context_vocabulary),
                bool(context_scenario),
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1000),
            )

            logger.debug(
                "generate_recommendations raw_response_length=%s,raw_response=%s",
                len(response.text),
                response.text,
            )

            # DRY: Use the helper to clean the response
            response_text = self._clean_json_response(response.text)

            recommendations = json.loads(response_text)

            if not isinstance(recommendations, list):
                recommendations = [recommendations]

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                "generate_recommendations success duration_ms=%.2f count=%s",
                duration_ms,
                len(recommendations),
            )

            return recommendations

        except json.JSONDecodeError as err:
            logger.warning("JSON parsing failed, attempting regex salvage. Error: %s", err)

            # Indestructible Regex Salvage: Hunt for the specific keys even in broken JSON
            sentences = re.findall(r'"sentence"\s*:\s*"([^"]+)"', response_text)
            reasons = re.findall(r'"reason"\s*:\s*"([^"]+)"', response_text)
            usages = re.findall(r'"usage"\s*:\s*"([^"]+)"', response_text)

            salvaged_recommendations = []
            for i in range(len(sentences)):
                salvaged_recommendations.append({
                    "sentence": sentences[i],
                    "reason": reasons[i] if i < len(reasons) else "A useful phrase for this scenario.",
                    "usage": usages[i] if i < len(usages) else "Use when appropriate in this context."
                })

            if salvaged_recommendations:
                duration_ms = (time.time() - start_time) * 1000
                logger.debug("generate_recommendations recovered via regex count=%s", len(salvaged_recommendations))
                return salvaged_recommendations

            duration_ms = (time.time() - start_time) * 1000
            logger.error("generate_recommendations salvage_failed duration_ms=%.2f error=%s", duration_ms, str(err))
            raise RuntimeError(f"Failed to parse LLM response: {err}") from err

        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("generate_recommendations failed duration_ms=%.2f error=%s", duration_ms, str(err))
            raise RuntimeError(f"LLM generation failed: {err}") from err

    def generate_practice_exercise(
        self, request: PracticeGenerateRequest
    ) -> PracticeExercise:
        """Generate a structured exercise based on the requested type."""
        start_time = time.time()

        # Define specific instructions based on the exercise type
        type_instructions = {
            "match-pairs": "Create 4 vocabulary matching pairs from the text. Format options as 'SourceWord|TargetWord'.",
            "complete-sentences": "Create a fill-in-the-blank sentence using the translation. Provide 4 options (1 correct, 3 distractors).",
            "translate-full-sentences": "Ask the user to translate the original text into the target language. Options array should be empty.",
            "complete-articles": "Create a fill-in-the-blank sentence focusing specifically on missing grammatical articles (the, a, der, la, etc.). Provide 4 article options."
        }

        instruction = type_instructions.get(request.exercise_type, type_instructions["complete-sentences"])

        prompt = f"""
You are an expert language tutor creating a practice exercise for a {request.current_level} level student learning {request.target_language.upper()}.

SEED CONTEXT:
- Source Text ({request.source_language.upper()}): "{request.original_text}"
- Target Translation ({request.target_language.upper()}): "{request.translation}"
- Context/Topic: {request.context_label}

EXERCISE TYPE: {request.exercise_type}
INSTRUCTION: {instruction}

Return ONLY a JSON object representing the exercise. Do not include markdown blocks. Format:
{{
  "type": "{request.exercise_type}",
  "prompt": "The sentence with ____ for blanks, or the instruction.",
  "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
  "correct_answer": "The exact correct option string",
  "explanation": "Brief explanation of why the answer is correct."
}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=800),
            )

            # DRY: Reuse the cleaning logic
            response_text = self._clean_json_response(response.text)
            data = json.loads(response_text)

            logger.debug("generate_practice_exercise success in %.2fms", (time.time() - start_time) * 1000)

            return PracticeExercise(
                type=data.get("type", request.exercise_type),
                prompt=data.get("prompt", ""),
                options=data.get("options", []),
                correct_answer=data.get("correct_answer", ""),
                explanation=data.get("explanation", "")
            )

        except Exception as err:
            logger.error("generate_practice_exercise failed: %s", err)
            # Safe fallback if generation fails
            return PracticeExercise(
                type=request.exercise_type,
                prompt="Failed to generate exercise. Please try again.",
                options=[],
                correct_answer="",
                explanation=str(err)
            )