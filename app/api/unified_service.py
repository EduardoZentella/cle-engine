"""Unified service coordinating all Phase 2 services into single interface."""

from __future__ import annotations

import logging
from uuid import UUID

from psycopg2.extras import RealDictCursor

from app.api.db import DatabasePool
from app.api.recommendation_pipeline import RecommendationPipeline
from app.api.schemas import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationItem,
    RecommendationMetadata,
    TranslateResponse,
    TranslateRequest,
    PracticeExercise,
    PracticeGenerateRequest,
    UserVerifyResponse,
    VocabularyUpsertItem,
    VocabularyBulkUpsertResponse,
)
from app.api.translation_service import TranslationService

logger = logging.getLogger(__name__)


class UnifiedRecommendationService:
    """Coordinates all recommendation services with simple public interface."""

    def __init__(
        self,
        database: DatabasePool,
        pipeline: RecommendationPipeline
    ):
        """Initialize with database and pipeline.

        Args:
            database: Database pool for user/vocabulary queries
            pipeline: Recommendation pipeline orchestrator
        """
        self.database = database
        self.pipeline = pipeline

    def _get_language_name(self, code: str | None) -> str:
        """Helper to map ISO codes to full language names."""
        if not code:
            return ""

        # Mapping dictionary
        language_map = {
            "es": "Spanish",
            "de": "German",
            "en": "English",
            "ru": "Russian",
            "fa": "Persian",
            "fr": "French",
            "it": "Italian"
        }

        # Return the mapped name, or default to uppercase code if not found
        return language_map.get(code.lower(), code.upper())

    def verify_user(self, name: str) -> UserVerifyResponse:
        """Verify if user exists by name.

        Args:
            name: Username or first name to search for

        Returns:
            UserVerifyResponse with exists, user_id, etc.
        """
        logger.debug("verify_user lookup name=%s", name)

        try:
            with self.database.connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, username, first_name, base_language, target_language, current_level, city
                        FROM users
                        WHERE LOWER(username) = LOWER(%s) OR LOWER(first_name) = LOWER(%s)
                        LIMIT 1
                        """,
                        (name, name),
                    )
                    result = cur.fetchone()

            if result:
                logger.debug(
                    "verify_user found id=%s username=%s",
                    result.get("id"),
                    result.get("username"),
                )

                base_lang_name = self._get_language_name(result.get("base_language"))
                target_lang_name = self._get_language_name(result.get("target_language"))
                return UserVerifyResponse(
                    exists=True,
                    user_id=UUID(str(result.get("id"))),
                    username=result.get("username"),
                    first_name=result.get("first_name"),
                    base_language=base_lang_name,
                    target_language=target_lang_name,
                    current_level=result.get("current_level"),
                    city=result.get("city"),
                )
            else:
                logger.debug("verify_user not found name=%s", name)
                return UserVerifyResponse(exists=False)

        except Exception as err:
            logger.error("verify_user failed error=%s", str(err))
            raise

    async def translate_text(self, payload: TranslateRequest) -> TranslateResponse:
        """Fast, standalone translation endpoint for UI responsiveness."""
        translation = self.pipeline.translation_service.translate(
            text=payload.original_text,
            source_lang=payload.source_language,
            target_lang=payload.target_language,
            user_level=payload.user_level,
        )
        return TranslateResponse(translation=translation)

    def generate_practice(self, payload: PracticeGenerateRequest) -> PracticeExercise:
        """Generate a dynamic practice exercise by routing directly to the LLM service."""
        return self.pipeline.llm_service.generate_practice_exercise(payload)

    async def generate_recommendations(
        self,
        payload: RecommendationGenerateRequest,
    ) -> RecommendationGenerateResponse:
        """Generate recommendations using full pipeline.

        Args:
            payload: Request with user_id, text, languages, context

        Returns:
            Response with translation, recommendations, metadata
        """
        logger.debug(
            "generate_recommendations start user_id=%s text_length=%s",
            payload.user_id,
            len(payload.original_text),
        )

        try:
            # Determine user level from database
            user_level = await self._get_user_level(payload.user_id)

            # Convert ContextScenario Pydantic model to a raw dictionary (ignoring nulls)
            context_dict = payload.context_scenario.model_dump(exclude_none=True) if payload.context_scenario else None

            # Execute pipeline
            result = await self.pipeline.execute(
                user_id=payload.user_id,
                original_text=payload.original_text,
                source_lang=payload.source_language,
                target_lang=payload.target_language,
                user_level=user_level,
                context_scenario=context_dict,
                translation_override=payload.translation,
            )

            # Format response
            recommendations = [
                RecommendationItem(
                    text=r["text"],
                    score=r["score"],
                    reason=r.get("reason"),
                    usage=r.get("usage")
                    )
                for r in result["recommendations"]
            ]

            response = RecommendationGenerateResponse(
                translation=result["translation"],
                recommendations=recommendations,
                metadata=RecommendationMetadata(
                    attempts=result["metadata"]["attempts"],
                    duration_ms=result["metadata"]["duration_ms"],
                ),
            )

            logger.debug(
                "generate_recommendations complete user_id=%s recommendation_count=%s",
                payload.user_id,
                len(recommendations),
            )

            return response

        except Exception as err:
            logger.error(
                "generate_recommendations failed user_id=%s error=%s",
                payload.user_id,
                str(err),
            )
            raise

    async def _get_user_level(self, user_id: UUID) -> str:
        """Get user's current proficiency level.

        Args:
            user_id: User ID

        Returns:
            Level code (A1, A2, B1, etc.) or default A1
        """
        try:
            with self.database.connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT current_level FROM users WHERE id = %s LIMIT 1",
                        (str(user_id),),
                    )
                    result = cur.fetchone()
                    return result.get("current_level", "A1") if result else "A1"
        except Exception:
            return "A1"  # Fallback to beginner level

    def bulk_upsert_vocabulary(
        self,
        items: list[VocabularyUpsertItem],
    ) -> VocabularyBulkUpsertResponse:
        """Bulk upsert vocabulary entries (admin endpoint).

        Args:
            items: List of vocabulary items to upsert

        Returns:
            Response with count of upserted items
        """
        logger.debug("bulk_upsert_vocabulary start item_count=%s", len(items))

        try:
            upserted_count = 0

            with self.database.connection() as conn:
                with conn.cursor() as cur:
                    for item in items:
                        cur.execute(
                            """
                            INSERT INTO vocabulary_entries
                            (word, meaning, description, category, cefr_level, tags,
                             source_language, target_language, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                            ON CONFLICT (word, source_language, target_language)
                            DO UPDATE SET
                                meaning = EXCLUDED.meaning,
                                description = EXCLUDED.description,
                                category = EXCLUDED.category,
                                cefr_level = EXCLUDED.cefr_level,
                                tags = EXCLUDED.tags
                            """,
                            (
                                item.word,
                                item.meaning,
                                item.description,
                                item.category,
                                item.cefr_level,
                                item.tags,
                                item.source_language,
                                item.target_language,
                            ),
                        )
                        upserted_count += 1

                conn.commit()

            logger.debug("bulk_upsert_vocabulary complete upserted=%s", upserted_count)

            return VocabularyBulkUpsertResponse(upserted=upserted_count)

        except Exception as err:
            logger.error("bulk_upsert_vocabulary failed error=%s", str(err))
            raise
