"""Async service layer for contextual recommendations and practice generation."""

from __future__ import annotations

import logging
from typing import Any, Sequence
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool

from app.api.config import Settings
from app.api.embeddings import EmbeddingProvider
from app.api.intelligence import IntelligenceContext, IntelligenceProvider
from app.api.pipeline.candidate_generator import HybridCandidateGenerator
from app.api.pipeline.contextual_pipeline import ContextualRecommendationPipeline
from app.api.pipeline.decision_policy import RecommendationDecisionPolicy
from app.api.pipeline.final_reranker import PretrainedModelFinalReranker
from app.api.perf_analytics import PerfAnalytics
from app.api.practice_engine import PracticeGenerator
from app.api.ranking_engine import CandidateRanker
from app.api.recommendation_repository import RecommendationRepository
from app.api.schemas import (
    PracticeExercise,
    PracticeResponse,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    UserUpsertRequest,
    UserUpsertResponse,
    VocabularyUpsertItem,
)


logger = logging.getLogger(__name__)


class RecommendationService:
    """Coordinates recommendation workflow across providers and repository."""

    def __init__(
        self,
        repository: RecommendationRepository,
        embedding_provider: EmbeddingProvider,
        intelligence_provider: IntelligenceProvider,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider
        self.intelligence_provider = intelligence_provider
        self.settings = settings
        self.ranker = CandidateRanker(settings)
        self.final_reranker = PretrainedModelFinalReranker(
            embedding_provider=embedding_provider,
            model_dir=settings.final_reranker_model_dir,
            manifest_file=settings.final_reranker_manifest_file,
        )
        self.candidate_generator = HybridCandidateGenerator(
            repository=repository,
            embedding_provider=embedding_provider,
            intelligence_provider=intelligence_provider,
            ranker=self.ranker,
            settings=settings,
        )
        self.decision_policy = RecommendationDecisionPolicy(
            final_k=settings.retrieval_final_k,
            approval_threshold=settings.relevance_approval_threshold,
            regenerate_threshold=settings.relevance_regenerate_threshold,
        )
        self.contextual_pipeline = ContextualRecommendationPipeline(
            generator=self.candidate_generator,
            final_reranker=self.final_reranker,
            decision_policy=self.decision_policy,
            ranker=self.ranker,
            settings=settings,
        )
        self.practice_generator = PracticeGenerator()

    async def aclose(self) -> None:
        """Dispose provider resources used by the service."""

        await self.final_reranker.aclose()
        await self.embedding_provider.aclose()
        await self.intelligence_provider.aclose()

    async def ping(self) -> bool:
        """Returns true when the database is reachable."""

        return await run_in_threadpool(self.repository.ping)

    def provider_health(self) -> dict[str, Any]:
        """Return provider degradation metrics for diagnostics and health endpoints."""

        return {
            "embedding": self.embedding_provider.health_snapshot(),
            "intelligence": self.intelligence_provider.health_snapshot(),
            "final_reranker": self.final_reranker.health_snapshot(),
        }

    async def upsert_user(self, payload: UserUpsertRequest) -> UserUpsertResponse:
        """Create or update user profile used by recommendation flows."""

        user_id = payload.user_id or uuid4()
        username = payload.username or f"user_{str(user_id)[:8]}"

        profile_vector_literal: str | None = None
        if payload.profile_summary:
            vector = await self.embedding_provider.embed(payload.profile_summary)
            profile_vector_literal = self._vector_to_literal(vector)

        created = await run_in_threadpool(
            self.repository.upsert_user,
            user_id=user_id,
            username=username,
            payload=payload,
            profile_vector_literal=profile_vector_literal,
        )
        return UserUpsertResponse(user_id=user_id, created=created)

    async def bulk_upsert_vocabulary(self, items: list[VocabularyUpsertItem]) -> int:
        """Load words/phrases that power semantic retrieval."""

        payload_texts: list[str] = []
        missing_indexes: list[int] = []
        prepared_embeddings: list[list[float] | None] = [None] * len(items)

        for index, item in enumerate(items):
            if item.embedding:
                prepared_embeddings[index] = item.embedding
                continue
            payload_text = " ".join(
                part for part in [item.word, item.description or "", item.meaning or ""] if part
            )
            missing_indexes.append(index)
            payload_texts.append(payload_text)

        if payload_texts:
            generated_vectors = await self.embedding_provider.embed_many(payload_texts)
            for generated_index, vector in enumerate(generated_vectors):
                item_index = missing_indexes[generated_index]
                prepared_embeddings[item_index] = vector

        vector_literals = [
            self._vector_to_literal(vector or [0.0] * self.settings.embedding_dimension)
            for vector in prepared_embeddings
        ]

        return await run_in_threadpool(
            self.repository.bulk_upsert_vocabulary,
            items,
            vector_literals,
        )

    async def generate_contextual_recommendations(
        self,
        payload: RecommendationRequest,
    ) -> RecommendationResponse:
        """Run contextual recommendation pipeline with explicit stage orchestration."""

        analytics = PerfAnalytics(
            logger=logger,
            scope="recommendation_service.generate_contextual_recommendations",
            context={"user_id": str(payload.user_id)},
        )
        try:
            with analytics.stage("run_contextual_pipeline", kind="compute"):
                pipeline_result = await self.contextual_pipeline.run(payload)

            with analytics.stage("persist_recommendation_outcome", kind="database"):
                await run_in_threadpool(
                    self.repository.persist_recommendation_outcome,
                    payload=payload,
                    translation_event_id=pipeline_result.translation_event_id,
                    retrieval_query=pipeline_result.context_text,
                    retrieval_vector_literal=pipeline_result.retrieval_vector_literal,
                    predicted_level=pipeline_result.predicted_level,
                    model_action=pipeline_result.model_action,
                    candidates=pipeline_result.candidates,
                    selected_candidates=pipeline_result.selected_candidates,
                    vector_count=pipeline_result.vector_count,
                    lexical_count=pipeline_result.lexical_count,
                    llm_count=pipeline_result.llm_count,
                    ml_approved_count=pipeline_result.ml_approved_count,
                    ml_total_count=len(pipeline_result.candidates),
                )

            with analytics.stage("build_recommendation_response", kind="compute"):
                if not pipeline_result.selected_candidates:
                    return RecommendationResponse(
                        predicted_level=pipeline_result.predicted_level,
                        model_action="fallback_llm",
                        reranked_recommendations=[
                            RecommendationItem(
                                phrase=payload.action.translation,
                                meaning=payload.action.original_text,
                                relevance=(
                                    "No vocabulary match found in the current index. "
                                    "Use fallback generation while expanding catalog entries."
                                ),
                                scores={"fusion": 0.0, "ml": 0.0},
                            )
                        ],
                    )

                return RecommendationResponse(
                    predicted_level=pipeline_result.predicted_level,
                    model_action=pipeline_result.model_action,
                    reranked_recommendations=[
                        RecommendationItem(
                            phrase=candidate["word"],
                            meaning=candidate.get("meaning"),
                            relevance=self.ranker.build_relevance(candidate),
                            scores={
                                "fusion": round(candidate["fusion_score"], 6),
                                "vector": round(candidate.get("vector_score") or 0.0, 6),
                                "lexical": round(candidate.get("lexical_score") or 0.0, 6),
                                "llm": round(candidate.get("llm_score") or 0.0, 6),
                                "ml": round(candidate.get("ml_relevance_score") or 0.0, 6),
                            },
                        )
                        for candidate in pipeline_result.selected_candidates
                    ],
                )
        finally:
            analytics.log_summary()

    async def generate_practice_exercises(self, user_id: UUID, limit: int = 5) -> PracticeResponse:
        """Generate structured context-relevant practice exercises."""

        safe_limit = max(1, min(limit, 12))
        rows = await run_in_threadpool(self.repository.fetch_practice_seed_rows, user_id, safe_limit)
        if not rows:
            return PracticeResponse(context_theme="General", exercises=[])

        context_theme = rows[0].get("category") or "General Vocabulary"
        focus_terms = [str(row.get("word")) for row in rows if row.get("word")]

        latest = await run_in_threadpool(self.repository.fetch_latest_user_context, user_id)
        intelligence_context = self._latest_intelligence_context_for_user(
            user_id=user_id,
            row=latest,
        )

        drafts = await self.intelligence_provider.generate_practice(
            context=intelligence_context,
            focus_terms=focus_terms,
            limit=safe_limit,
        )
        if not drafts:
            drafts = self.practice_generator.fallback_practice_drafts(
                focus_terms=focus_terms,
                context_theme=context_theme,
                limit=safe_limit,
            )

        exercises = [
            PracticeExercise(
                type=draft.exercise_type,
                prompt=draft.prompt,
                options=draft.options,
                correct_answer=draft.correct_answer,
                explanation=draft.explanation,
            )
            for draft in drafts[:safe_limit]
        ]

        await run_in_threadpool(
            self.repository.persist_practice_session,
            user_id=user_id,
            context_theme=context_theme,
            exercises=exercises,
        )

        return PracticeResponse(context_theme=context_theme, exercises=exercises)

    def _latest_intelligence_context_for_user(
        self,
        *,
        user_id: UUID,
        row: dict[str, Any],
    ) -> IntelligenceContext:
        return IntelligenceContext(
            user_id=str(user_id),
            predicted_level=row.get("current_level") or "A1",
            source_text=row.get("source_text") or "",
            translated_text=row.get("translated_text") or "",
            source_language=row.get("base_language") or "en",
            target_language=row.get("target_language") or "de",
            location=row.get("location"),
            environment=row.get("environment"),
            sentiment=row.get("sentiment"),
            intent=row.get("intent"),
        )

    @staticmethod
    def _vector_to_literal(vector: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
