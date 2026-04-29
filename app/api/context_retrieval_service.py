"""Context retrieval service - Get vocabulary and context for recommendations."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from psycopg2.extras import RealDictCursor

from app.api.db import DatabasePool
from app.api.embeddings_provider_gemini import GeminiEmbeddingProvider

logger = logging.getLogger(__name__)


class ContextRetrievalService:
    """Retrieve vocabulary entries and context metadata using vector similarity."""

    def __init__(self, database: DatabasePool, embedding_provider: GeminiEmbeddingProvider):
        """Initialize with database and embedding provider."""
        self.database = database
        self.embedding_provider = embedding_provider

    def retrieve_context(
        self,
        user_id: UUID,
        original_text: str,
        source_lang: str,
        target_lang: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant vocabulary and context for a user.

        Args:
            user_id: User ID for personalization
            original_text: The text user is translating
            source_lang: Source language
            target_lang: Target language
            limit: Max results to return

        Returns:
            List of {word, meaning, category, cefr_level, context_metadata}
        """
        start_time = time.time()

        try:
            logger.debug(
                "retrieve_context start user_id=%s text_length=%s source=%s target=%s limit=%s",
                user_id,
                len(original_text),
                source_lang,
                target_lang,
                limit,
            )

            # Embed the input text
            query_embedding = self.embedding_provider.sync_embed(original_text)

            # Vector similarity search in database
            with self.database.connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT
                            word,
                            meaning,
                            category,
                            cefr_level,
                            tags,
                            (embedding <-> %s::vector) AS distance,
                            (1 - (embedding <-> %s::vector) / 2) AS similarity_score
                        FROM vocabulary_entries
                        WHERE source_language = %s
                          AND target_language = %s
                          AND is_active = TRUE
                        ORDER BY embedding <-> %s::vector ASC
                        LIMIT %s
                        """,
                        (
                            query_embedding,
                            query_embedding,
                            source_lang,
                            target_lang,
                            query_embedding,
                            limit,
                        ),
                    )

                    results = [dict(row) for row in cur.fetchall()]

            duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                "retrieve_context success user_id=%s duration_ms=%.2f results=%s",
                user_id,
                duration_ms,
                len(results),
            )

            return results

        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "retrieve_context failed user_id=%s duration_ms=%.2f error=%s",
                user_id,
                duration_ms,
                str(err),
            )
            raise RuntimeError(f"Context retrieval failed: {err}") from err
