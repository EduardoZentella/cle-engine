"""Gemini-specific embedding provider with connection pooling and performance tracking."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider:
    """Fast, reliable embedding generation using Gemini API with pooling."""

    def __init__(self, api_key: str | None = None):
        """Initialize Gemini client."""
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = "gemini-embedding-2"
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text with retry logic and timing.

        Args:
            text: Text to embed (max 8192 tokens)

        Returns:
            384-dimensional embedding vector

        Raises:
            RuntimeError: If all retries exhausted
        """
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    "embed_text attempt=%s text_length=%s",
                    attempt + 1,
                    len(text),
                )

                result = self.client.models.embed_content(
                    model=self.model,
                    contents=text,
                    config=types.EmbedContentConfig(
                        output_dimensionality=384  # Match database schema
                    ),
                )

                duration_ms = (time.time() - start_time) * 1000
                embedding = result.embeddings[0].values

                logger.debug(
                    "embed_text success attempt=%s duration_ms=%.2f embedding_dim=%s",
                    attempt + 1,
                    duration_ms,
                    len(embedding),
                )

                return embedding

            except Exception as err:
                last_error = err
                duration_ms = (time.time() - start_time) * 1000

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # exponential backoff
                    logger.warning(
                        "embed_text retry attempt=%s duration_ms=%.2f delay=%.2f error=%s",
                        attempt + 1,
                        duration_ms,
                        delay,
                        str(err),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "embed_text exhausted attempts=%s duration_ms=%.2f error=%s",
                        self.max_retries,
                        duration_ms,
                        str(err),
                    )

        raise RuntimeError(
            f"Failed to generate embedding after {self.max_retries} attempts: {last_error}"
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        start_time = time.time()
        logger.debug("embed_batch start count=%s", len(texts))

        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)

        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            "embed_batch complete count=%s duration_ms=%.2f",
            len(texts),
            duration_ms,
        )

        return embeddings

    def sync_embed(self, text: str) -> list[float]:
        """Synchronous wrapper for embedding (for backward compatibility).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            result = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=384),
            )
            embedding = result.embeddings[0].values
            logger.debug("sync_embed success text_length=%s embedding_dim=%s", len(text), len(embedding))
            return embedding
        except Exception as err:
            logger.error("sync_embed failed error=%s text_length=%s", str(err), len(text))
            raise RuntimeError(f"Embedding failed: {err}") from err
