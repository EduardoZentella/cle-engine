"""Candidate generation stage for contextual recommendation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Sequence

from fastapi.concurrency import run_in_threadpool

from app.api.config import Settings
from app.api.embeddings import EmbeddingProvider
from app.api.intelligence import IntelligenceContext, IntelligenceProvider
from app.api.perf_analytics import PerfAnalytics
from app.api.ranking_engine import CandidateRanker
from app.api.recommendation_repository import RecommendationRepository
from app.api.schemas import RecommendationRequest


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CandidateGenerationResult:
    """Output payload from candidate generation stage."""

    predicted_level: str
    translation_event_id: str
    context_text: str
    retrieval_vector_literal: str
    vector_rows: list[dict[str, Any]]
    lexical_rows: list[dict[str, Any]]
    llm_draft_count: int
    candidates: list[dict[str, Any]]
    intelligence_context: IntelligenceContext


class HybridCandidateGenerator:
    """Generates candidate recommendations from retrieval plus draft generation."""

    def __init__(
        self,
        *,
        repository: RecommendationRepository,
        embedding_provider: EmbeddingProvider,
        intelligence_provider: IntelligenceProvider,
        ranker: CandidateRanker,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._intelligence_provider = intelligence_provider
        self._ranker = ranker
        self._settings = settings

    async def generate_initial(self, payload: RecommendationRequest) -> CandidateGenerationResult:
        """Generate initial hybrid candidate pool for reranking."""

        analytics = PerfAnalytics(
            logger=logger,
            scope="candidate_generator.generate_initial",
            context={"user_id": str(payload.user_id)},
        )
        try:
            with analytics.stage("build_context_text", kind="compute"):
                context_text = self._build_context_text(payload)

            with analytics.stage("embed_context_text", kind="network"):
                retrieval_vector = await self._embedding_provider.embed(context_text)
                retrieval_vector_literal = self._vector_to_literal(retrieval_vector)

            context_json = payload.action.context.model_dump(exclude_none=True)
            with analytics.stage("prepare_recommendation_context", kind="database"):
                prepared = await run_in_threadpool(
                    self._repository.prepare_recommendation_context,
                    payload,
                    context_text,
                    context_json,
                    retrieval_vector_literal,
                )

            predicted_level = str(prepared["predicted_level"])
            translation_event_id = str(prepared["translation_event_id"])
            vector_rows = list(prepared["vector_rows"])
            lexical_rows = list(prepared["lexical_rows"])

            with analytics.stage("build_intelligence_context", kind="compute"):
                intelligence_context = self._build_intelligence_context(
                    payload=payload,
                    predicted_level=predicted_level,
                )

            with analytics.stage("generate_llm_drafts", kind="network"):
                llm_drafts = await self._intelligence_provider.generate_recommendations(
                    context=intelligence_context,
                    limit=max(self._settings.retrieval_final_k * 2, 8),
                )
                llm_draft_count = len(llm_drafts)

            with analytics.stage("map_llm_drafts", kind="database"):
                llm_rows = await run_in_threadpool(
                    self._repository.map_llm_drafts,
                    source_language=payload.action.source_language,
                    target_language=payload.action.target_language,
                    llm_drafts=llm_drafts,
                )

            with analytics.stage("fuse_candidates", kind="compute"):
                candidates = self._ranker.fuse_candidates(vector_rows, lexical_rows, llm_rows)

            return CandidateGenerationResult(
                predicted_level=predicted_level,
                translation_event_id=translation_event_id,
                context_text=context_text,
                retrieval_vector_literal=retrieval_vector_literal,
                vector_rows=vector_rows,
                lexical_rows=lexical_rows,
                llm_draft_count=llm_draft_count,
                candidates=candidates,
                intelligence_context=intelligence_context,
            )
        finally:
            analytics.log_summary()

    async def regenerate(
        self,
        payload: RecommendationRequest,
        *,
        seed: CandidateGenerationResult,
    ) -> tuple[list[dict[str, Any]], int]:
        """Regenerate candidate drafts and produce a new hybrid pool."""

        analytics = PerfAnalytics(
            logger=logger,
            scope="candidate_generator.regenerate",
            context={"user_id": str(payload.user_id)},
        )
        try:
            with analytics.stage("build_regen_context", kind="compute"):
                regen_context = IntelligenceContext(
                    user_id=seed.intelligence_context.user_id,
                    predicted_level=seed.intelligence_context.predicted_level,
                    source_text=seed.intelligence_context.source_text,
                    translated_text=seed.intelligence_context.translated_text,
                    source_language=seed.intelligence_context.source_language,
                    target_language=seed.intelligence_context.target_language,
                    location=seed.intelligence_context.location,
                    environment=seed.intelligence_context.environment,
                    sentiment=seed.intelligence_context.sentiment,
                    intent=seed.intelligence_context.intent,
                    ocr_text=seed.intelligence_context.ocr_text,
                    topic=(
                        "regenerate recommendations for low relevance in context: "
                        f"{seed.intelligence_context.topic or 'general'}"
                    ),
                )

            with analytics.stage("generate_regenerated_drafts", kind="network"):
                regenerated_drafts = await self._intelligence_provider.generate_recommendations(
                    context=regen_context,
                    limit=max(self._settings.retrieval_final_k * 2, 8),
                )

            with analytics.stage("map_regenerated_drafts", kind="database"):
                regenerated_rows = await run_in_threadpool(
                    self._repository.map_llm_drafts,
                    source_language=payload.action.source_language,
                    target_language=payload.action.target_language,
                    llm_drafts=regenerated_drafts,
                )

            with analytics.stage("fuse_regenerated_candidates", kind="compute"):
                candidates = self._ranker.fuse_candidates(
                    seed.vector_rows,
                    seed.lexical_rows,
                    regenerated_rows,
                )

            return candidates, len(regenerated_drafts)
        finally:
            analytics.log_summary()

    @staticmethod
    def _build_intelligence_context(
        payload: RecommendationRequest,
        predicted_level: str,
    ) -> IntelligenceContext:
        return IntelligenceContext(
            user_id=str(payload.user_id),
            predicted_level=predicted_level,
            source_text=payload.action.original_text,
            translated_text=payload.action.translation,
            source_language=payload.action.source_language,
            target_language=payload.action.target_language,
            location=payload.action.context.location,
            environment=payload.action.context.environment,
            sentiment=payload.action.context.sentiment,
            intent=payload.action.context.intent,
            ocr_text=payload.action.ocr_text,
            topic=payload.action.context.topic,
        )

    @staticmethod
    def _build_context_text(payload: RecommendationRequest) -> str:
        chunks = [
            f"Original text: {payload.action.original_text}",
            f"Translation: {payload.action.translation}",
            f"Source language: {payload.action.source_language}",
            f"Target language: {payload.action.target_language}",
            f"Input mode: {payload.action.input_mode}",
        ]

        if payload.action.ocr_text:
            chunks.append(f"OCR text: {payload.action.ocr_text}")

        if payload.action.context.location:
            chunks.append(f"Location: {payload.action.context.location}")
        if payload.action.context.environment:
            chunks.append(f"Environment: {payload.action.context.environment}")
        if payload.action.context.sentiment:
            chunks.append(f"Sentiment: {payload.action.context.sentiment}")
        if payload.action.context.intent:
            chunks.append(f"Intent: {payload.action.context.intent}")
        if payload.action.context.topic:
            chunks.append(f"Topic: {payload.action.context.topic}")

        return " | ".join(chunks)

    @staticmethod
    def _vector_to_literal(vector: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
