"""Decision policy stage for contextual recommendation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DecisionResult:
    """Decision output after reranking stage."""

    model_action: str
    requires_regeneration: bool
    approved_candidates: list[dict[str, Any]]
    approval_ratio: float


class RecommendationDecisionPolicy:
    """Applies deterministic policy to choose use vs regenerate behavior."""

    def __init__(
        self,
        *,
        final_k: int,
        approval_threshold: float,
        regenerate_threshold: float,
    ) -> None:
        self._final_k = final_k
        self._approval_threshold = approval_threshold
        self._regenerate_threshold = regenerate_threshold

    def decide(self, candidates: list[dict[str, Any]]) -> DecisionResult:
        if not candidates:
            return DecisionResult(
                model_action="fallback_llm",
                requires_regeneration=False,
                approved_candidates=[],
                approval_ratio=0.0,
            )

        approved_candidates = [candidate for candidate in candidates if candidate.get("ml_approved")]
        top_window = max(1, min(len(candidates), self._final_k))
        approval_ratio = len(approved_candidates) / top_window

        if approval_ratio < self._regenerate_threshold:
            return DecisionResult(
                model_action="regenerate_with_llm",
                requires_regeneration=True,
                approved_candidates=approved_candidates,
                approval_ratio=approval_ratio,
            )

        if approval_ratio < self._approval_threshold:
            return DecisionResult(
                model_action="manual_review",
                requires_regeneration=False,
                approved_candidates=approved_candidates,
                approval_ratio=approval_ratio,
            )

        return DecisionResult(
            model_action="use_retrieved",
            requires_regeneration=False,
            approved_candidates=approved_candidates,
            approval_ratio=approval_ratio,
        )
