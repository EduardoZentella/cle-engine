"""Practice exercise generation utilities."""

from __future__ import annotations

from typing import Sequence

from app.api.intelligence import PracticeDraft


class PracticeGenerator:
    """Builds deterministic fallback practice drafts when model output is unavailable."""

    @staticmethod
    def fallback_practice_drafts(
        focus_terms: Sequence[str],
        context_theme: str,
        limit: int,
    ) -> list[PracticeDraft]:
        drafts: list[PracticeDraft] = []
        exercise_types = [
            "multiple_choice",
            "fill_in_the_blank",
            "translation",
            "open_response",
        ]
        for index, term in enumerate(focus_terms[:limit], start=1):
            exercise_type = exercise_types[(index - 1) % len(exercise_types)]
            if exercise_type == "multiple_choice":
                drafts.append(
                    PracticeDraft(
                        exercise_type=exercise_type,
                        prompt=f"Choose the best meaning for '{term}'.",
                        options=[
                            f"Contextual meaning of {term}",
                            f"Opposite of {term}",
                            f"Unrelated phrase in {context_theme}",
                            f"Literal typo of {term}",
                        ],
                        correct_answer=f"Contextual meaning of {term}",
                        explanation="Fallback multiple-choice exercise.",
                    )
                )
            elif exercise_type == "fill_in_the_blank":
                drafts.append(
                    PracticeDraft(
                        exercise_type=exercise_type,
                        prompt=f"Fill in the blank with '{term}' in a {context_theme} sentence.",
                        correct_answer=term,
                        explanation="Fallback fill-in-the-blank exercise.",
                    )
                )
            elif exercise_type == "translation":
                drafts.append(
                    PracticeDraft(
                        exercise_type=exercise_type,
                        prompt=f"Translate a sentence that naturally uses '{term}' in {context_theme}.",
                        explanation="Fallback translation exercise.",
                    )
                )
            else:
                drafts.append(
                    PracticeDraft(
                        exercise_type=exercise_type,
                        prompt=f"Write a short response where '{term}' is relevant in {context_theme}.",
                        explanation="Fallback open-response exercise.",
                    )
                )

        return drafts
