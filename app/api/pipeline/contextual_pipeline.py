"""Contextual recommendation pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.api.config import Settings
from app.api.perf_analytics import PerfAnalytics
from app.api.pipeline.candidate_generator import CandidateGenerationResult, HybridCandidateGenerator
from app.api.pipeline.decision_policy import RecommendationDecisionPolicy
from app.api.pipeline.final_reranker import FinalReranker
from app.api.ranking_engine import CandidateRanker
from app.api.schemas import RecommendationRequest


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineRunResult:
    """Final contextual recommendation pipeline output."""

    predicted_level: str
    model_action: str
    context_text: str
    retrieval_vector_literal: str
    translation_event_id: str
    candidates: list[dict[str, Any]]
    selected_candidates: list[dict[str, Any]]
    vector_count: int
    lexical_count: int
    llm_count: int
    ml_approved_count: int


class ContextualRecommendationPipeline:
    """Runs generation -> final reranking -> policy decision stages."""

    def __init__(
        self,
        *,
        generator: HybridCandidateGenerator,
        final_reranker: FinalReranker,
        decision_policy: RecommendationDecisionPolicy,
        ranker: CandidateRanker,
        settings: Settings,
    ) -> None:
        self._generator = generator
        self._final_reranker = final_reranker
        self._decision_policy = decision_policy
        self._ranker = ranker
        self._settings = settings

    async def run(self, payload: RecommendationRequest) -> PipelineRunResult:
        """Execute complete contextual recommendation pipeline."""

        analytics = PerfAnalytics(
            logger=logger,
            scope="contextual_pipeline.run",
            context={"user_id": str(payload.user_id)},
        )
        try:
            with analytics.stage("generate_initial_candidates", kind="compute"):
                initial = await self._generator.generate_initial(payload)

            with analytics.stage("final_rerank_initial", kind="compute"):
                reranked_candidates = await self._final_reranker.rerank(
                    context=initial.intelligence_context,
                    candidates=initial.candidates,
                    approval_threshold=self._settings.relevance_approval_threshold,
                )

            with analytics.stage("decision_initial", kind="compute"):
                decision = self._decision_policy.decide(reranked_candidates)
            llm_count = initial.llm_draft_count
            final_candidates = reranked_candidates
            model_action = decision.model_action

            if decision.requires_regeneration:
                with analytics.stage("regenerate_candidates", kind="compute"):
                    regenerated_candidates, regenerated_llm_count = await self._generator.regenerate(
                        payload,
                        seed=initial,
                    )
                llm_count = max(llm_count, regenerated_llm_count)

                with analytics.stage("final_rerank_regenerated", kind="compute"):
                    final_candidates = await self._final_reranker.rerank(
                        context=initial.intelligence_context,
                        candidates=regenerated_candidates,
                        approval_threshold=self._settings.relevance_approval_threshold,
                    )

                with analytics.stage("decision_regenerated", kind="compute"):
                    decision = self._decision_policy.decide(final_candidates)
                model_action = "regenerate_with_llm" if final_candidates else "fallback_llm"

            with analytics.stage("annotate_and_select", kind="compute"):
                selected_pool = (
                    decision.approved_candidates if decision.approved_candidates else final_candidates
                )
                selected_candidates = selected_pool[: self._settings.retrieval_final_k]
                selected_ids = {str(candidate["vocabulary_id"]) for candidate in selected_candidates}

                for index, candidate in enumerate(final_candidates, start=1):
                    candidate["rank_position"] = index
                    candidate["selected"] = str(candidate["vocabulary_id"]) in selected_ids
                    candidate["relevance_reason"] = self._ranker.build_relevance(candidate)

                ml_approved_count = len(
                    [candidate for candidate in final_candidates if candidate.get("ml_approved")]
                )

            return PipelineRunResult(
                predicted_level=initial.predicted_level,
                model_action=model_action,
                context_text=initial.context_text,
                retrieval_vector_literal=initial.retrieval_vector_literal,
                translation_event_id=initial.translation_event_id,
                candidates=final_candidates,
                selected_candidates=selected_candidates,
                vector_count=len(initial.vector_rows),
                lexical_count=len(initial.lexical_rows),
                llm_count=llm_count,
                ml_approved_count=ml_approved_count,
            )
        finally:
            analytics.log_summary()
