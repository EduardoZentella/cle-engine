"""Recommendation pipeline orchestrator - coordinates all stages in linear flow."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from app.api.context_retrieval_service import ContextRetrievalService
from app.api.debug_logger import DebugLogger
from app.api.embeddings_provider_gemini import GeminiEmbeddingProvider
from app.api.evaluation_service import EvaluationService
from app.api.llm_generation_service import LLMGenerationService
from app.api.performance_metrics import MetricStatus, PerformanceTracker
from app.api.translation_service import TranslationService

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    """Execute the linear recommendation pipeline with full observability."""

    def __init__(
        self,
        translation_service: TranslationService,
        context_service: ContextRetrievalService,
        llm_service: LLMGenerationService,
        evaluation_service: EvaluationService,
        performance_tracker: PerformanceTracker,
        debug_logger: DebugLogger,
    ):
        """Initialize pipeline with all services."""
        self.translation_service = translation_service
        self.context_service = context_service
        self.llm_service = llm_service
        self.evaluation_service = evaluation_service
        self.performance_tracker = performance_tracker
        self.debug_logger = debug_logger

    async def execute(
        self,
        user_id: UUID,
        original_text: str,
        source_lang: str,
        target_lang: str,
        user_level: str,
        context_scenario: dict[str, Any] | None = None,
        translation_override: str | None = None,
    ) -> dict[str, Any]:
        """Execute the full recommendation pipeline."""
        pipeline_start = time.time()

        try:
            self.debug_logger.log_event(
                "info",
                "Pipeline started",
                user_id=str(user_id),
                stage="pipeline",
                context={"source": source_lang, "target": target_lang},
            )



            # Stage 1: TRANSLATE
            if translation_override:
                translation = translation_override
            else:
                translation = self._stage_translate(
                    original_text, source_lang, target_lang, user_level
                )

            # Stage 2: RETRIEVE CONTEXT
            context = self._stage_retrieve(
                user_id, original_text, source_lang, target_lang
            )

            # Stage 3-4: GENERATE & EVALUATE (with retry loop)
            # <-- 2. Pass target_lang and context_scenario downwards
            recommendations, attempts = await self._stage_generate_and_evaluate(
                original_text, translation, context, user_level, target_lang, context_scenario
            )

            pipeline_duration_ms = (time.time() - pipeline_start) * 1000

            self.debug_logger.log_event(
                "info",
                "Pipeline completed successfully",
                user_id=str(user_id),
                stage="pipeline",
                context={
                    "attempts": attempts,
                    "duration_ms": pipeline_duration_ms,
                    "recommendation_count": len(recommendations),
                },
            )

            return {
                "translation": translation,
                "recommendations": recommendations[:3],  # Top 3
                "metadata": {
                    "attempts": attempts,
                    "duration_ms": pipeline_duration_ms,
                },
            }

        except Exception as err:
            pipeline_duration_ms = (time.time() - pipeline_start) * 1000
            self.debug_logger.log_event(
                "error",
                f"Pipeline failed: {str(err)}",
                user_id=str(user_id),
                stage="pipeline",
                context={"duration_ms": pipeline_duration_ms},
            )
            raise RuntimeError(f"Recommendation pipeline failed: {err}") from err

    def _stage_translate(
        self, original_text: str, source_lang: str, target_lang: str, user_level: str
    ) -> str:
        """Execute translate stage."""
        stage_start = time.time()
        try:
            logger.debug("stage_translate start")
            translation = self.translation_service.translate(
                original_text, source_lang, target_lang, user_level
            )

            duration_ms = (time.time() - stage_start) * 1000
            self.performance_tracker.record(
                stage="translate", duration_ms=duration_ms, status=MetricStatus.SUCCESS
            )
            logger.debug("stage_translate complete duration_ms=%.2f", duration_ms)
            return translation

        except Exception as err:
            duration_ms = (time.time() - stage_start) * 1000
            self.performance_tracker.record(
                stage="translate", duration_ms=duration_ms, status=MetricStatus.ERROR
            )
            raise

    def _stage_retrieve(
        self,
        user_id: UUID,
        original_text: str,
        source_lang: str,
        target_lang: str,
    ) -> list[dict[str, Any]]:
        """Execute retrieve stage."""
        stage_start = time.time()
        try:
            logger.debug("stage_retrieve start")
            context = self.context_service.retrieve_context(
                user_id, original_text, source_lang, target_lang, limit=15
            )

            duration_ms = (time.time() - stage_start) * 1000
            self.performance_tracker.record(
                stage="retrieve",
                duration_ms=duration_ms,
                status=MetricStatus.SUCCESS,
                user_id=str(user_id),
                metadata={"context_count": len(context)},
            )
            logger.debug("stage_retrieve complete duration_ms=%.2f", duration_ms)
            return context

        except Exception as err:
            duration_ms = (time.time() - stage_start) * 1000
            self.performance_tracker.record(
                stage="retrieve", duration_ms=duration_ms, status=MetricStatus.ERROR, user_id=str(user_id)
            )
            raise

    async def _stage_generate_and_evaluate(
        self,
        original_text: str,
        translation: str,
        context: list[dict[str, Any]],
        user_level: str,
        target_lang: str,                               # <-- 3. Accept target_lang
        context_scenario: dict[str, Any] | None = None, # <-- 4. Accept scenario
    ) -> tuple[list[dict[str, Any]], int]:
        """Execute generate & evaluate stages with retry loop."""
        max_attempts = 3
        final_recommendations = []
        attempt = 0

        for attempt in range(1, max_attempts + 1):
            stage_start = time.time()

            try:
                logger.debug("stage_generate attempt=%s", attempt)

                # 5. Get rich dictionaries from LLM
                candidates_rich = self.llm_service.generate_recommendations(
                    original_text, translation, context, user_level, target_lang, context_scenario
                )

                # 6. Extract just the strings for the Evaluation Service embedding
                candidate_sentences = [c.get("sentence", "") for c in candidates_rich if c.get("sentence")]

                logger.debug("stage_evaluate attempt=%s", attempt)
                scored_results, meets_threshold = (
                    await self.evaluation_service.evaluate_recommendations(
                        candidate_sentences, original_text, context
                    )
                )

                # 7. Merge the Evaluator's scores with the LLM's rich metadata
                final_recommendations = []
                for scored_item in scored_results:
                    for rich_item in candidates_rich:
                        if rich_item.get("sentence") == scored_item["text"]:
                            final_recommendations.append({
                                "text": scored_item["text"],
                                "score": scored_item["score"],
                                "reason": rich_item.get("reason", ""),
                                "usage": rich_item.get("usage", "")
                            })
                            break

                duration_ms = (time.time() - stage_start) * 1000

                # Safely calculate the max score from the list of dictionaries
                current_max_score = max((rec["score"] for rec in final_recommendations), default=0.0)

                if meets_threshold:
                    self.performance_tracker.record(
                        stage="generate", duration_ms=duration_ms, status=MetricStatus.SUCCESS,
                        attempt=attempt, metadata={"candidate_count": len(final_recommendations), "max_score": current_max_score},
                    )
                    break
                else:
                    if attempt < max_attempts:
                        self.performance_tracker.record(
                            stage="generate", duration_ms=duration_ms, status=MetricStatus.RETRY,
                            attempt=attempt, metadata={"max_score": current_max_score, "threshold": self.evaluation_service.similarity_threshold},
                        )
                    else:
                        self.performance_tracker.record(
                            stage="generate", duration_ms=duration_ms, status=MetricStatus.SUCCESS,
                            attempt=attempt, metadata={"max_score": current_max_score, "note": "accepted_below_threshold"},
                        )
                        break

            except Exception as err:
                duration_ms = (time.time() - stage_start) * 1000
                self.performance_tracker.record(
                    stage="generate", duration_ms=duration_ms, status=MetricStatus.ERROR, attempt=attempt
                )
                if attempt < max_attempts:
                    logger.warning("Attempt %s failed with error: %s. Retrying...", attempt, err)
                    continue
                raise

        return final_recommendations, attempt