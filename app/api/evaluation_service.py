"""Evaluation service - Score generated sentences against context."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.api.embeddings_provider_gemini import GeminiEmbeddingProvider

logger = logging.getLogger(__name__)


class EvaluationService:
    """Evaluate and score generated sentence recommendations."""

    def __init__(self, embedding_provider: GeminiEmbeddingProvider):
        """Initialize with embedding provider for similarity scoring."""
        self.embedding_provider = embedding_provider
        self.similarity_threshold = 0.7  # Min score to accept recommendation
        self.max_retries = 3

    async def evaluate_recommendations(
        self,
        candidates: list[str],
        original_text: str,
        context_vocabulary: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Evaluate candidate sentences and determine if they meet criteria.

        Args:
            candidates: List of candidate sentences to evaluate
            original_text: Reference text for semantic matching
            context_vocabulary: Available vocabulary context

        Returns:
            Tuple of (scored_candidates, meets_threshold)
            Where scored_candidates = [{text, score}, ...]
            And meets_threshold = True if best score >= threshold

        Raises:
            RuntimeError: If evaluation fails
        """
        start_time = time.time()

        try:
            logger.debug(
                "evaluate_recommendations start candidate_count=%s threshold=%.2f",
                len(candidates),
                self.similarity_threshold,
            )

            # Get embeddings for all candidates and original text
            original_embedding = await self.embedding_provider.embed(original_text)
            candidate_embeddings = await self.embedding_provider.embed_batch(candidates)

            # Calculate cosine similarity between original and each candidate
            scored_candidates = []
            for candidate, embedding in zip(candidates, candidate_embeddings):
                similarity = self._cosine_similarity(original_embedding, embedding)
                scored_candidates.append({
                    "text": candidate,
                    "score": round(similarity, 3),
                })

            # Sort by score descending
            scored_candidates.sort(key=lambda x: x["score"], reverse=True)

            max_score = scored_candidates[0]["score"] if scored_candidates else 0
            meets_threshold = max_score >= self.similarity_threshold

            duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                "evaluate_recommendations complete duration_ms=%.2f max_score=%.3f meets_threshold=%s",
                duration_ms,
                max_score,
                meets_threshold,
            )

            return scored_candidates, meets_threshold

        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "evaluate_recommendations failed duration_ms=%.2f error=%s",
                duration_ms,
                str(err),
            )
            raise RuntimeError(f"Evaluation failed: {err}") from err

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Similarity score between -1 and 1
        """
        if len(vec_a) != len(vec_b):
            raise ValueError("Vectors must have same dimension")

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = sum(a ** 2 for a in vec_a) ** 0.5
        magnitude_b = sum(b ** 2 for b in vec_b) ** 0.5

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    def should_retry(self, attempt: int, max_score: float) -> bool:
        """Determine if evaluation should retry LLM generation.

        Args:
            attempt: Current attempt number (1-indexed)
            max_score: Best score from evaluation

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False

        if max_score >= self.similarity_threshold:
            return False

        return True
