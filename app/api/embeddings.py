"""Embedding providers used by recommendation retrieval.

Available implementations:

- `HashEmbeddingProvider`: deterministic, local fallback provider.
- `SentenceTransformerEmbeddingProvider`: in-process sentence-transformers model.
- `LLMApiEmbeddingProvider`: external LLM embedding API provider (OpenAI-compatible).

Provider selection is done through `build_embedding_provider`.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import logging
import math
import random
import threading
from typing import Any, Protocol, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.api.config import Settings
from app.api.perf_analytics import PerfAnalytics
from app.api.provider_health import ProviderHealth

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Provides normalized embeddings for retrieval queries."""

    dimension: int

    async def embed(self, text: str) -> list[float]:
        """Return a normalized vector representation for input text."""

        ...

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized vectors for multiple inputs."""

        ...

    def health_snapshot(self) -> dict[str, Any]:
        """Return current provider degradation/health metrics."""

        ...

    async def aclose(self) -> None:
        """Release provider resources."""

        ...


def _normalize_vector(vector: list[float], dimension: int) -> list[float]:
    """Resize to expected dimension and L2-normalize values."""

    if not vector:
        return [0.0] * dimension

    resized: list[float]
    source_dimension = len(vector)
    if source_dimension == dimension:
        resized = vector
    elif source_dimension > dimension:
        bucket_size = source_dimension / dimension
        reduced: list[float] = []
        for index in range(dimension):
            start = int(index * bucket_size)
            end = int((index + 1) * bucket_size)
            if end <= start:
                end = min(source_dimension, start + 1)
            chunk = vector[start:end]
            reduced.append(sum(chunk) / len(chunk))
        resized = reduced
    else:
        resized = vector + ([0.0] * (dimension - source_dimension))

    norm = math.sqrt(sum(value * value for value in resized))
    if norm == 0.0:
        return [0.0] * dimension
    return [float(value / norm) for value in resized]


def _build_retry_session() -> requests.Session:
    """Create a requests session with connection pooling and retries."""

    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("POST",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class HashEmbeddingProvider:
    """Deterministic fallback embedding provider with no external dependencies."""

    def __init__(self, dimension: int = 384) -> None:
        """Create a deterministic pseudo-embedding provider."""

        self.dimension = dimension
        self._health = ProviderHealth(
            name="embedding",
            backend="hash",
            max_consecutive_failures=1,
        )

    async def embed(self, text: str) -> list[float]:
        """Generate a deterministic normalized vector from text.

        This implementation is intended for development and tests where stable
        output is more important than semantic quality.
        """

        seed = int.from_bytes(
            hashlib.sha256(text.encode("utf-8")).digest()[:8],
            byteorder="big",
            signed=False,
        )
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
        self._health.record_success()
        return _normalize_vector(vector, self.dimension)

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [await self.embed(text) for text in texts]

    def health_snapshot(self) -> dict[str, Any]:
        return self._health.snapshot()

    async def aclose(self) -> None:
        return None


class SentenceTransformerEmbeddingProvider:
    """Embedding provider that loads sentence-transformers model in-process."""

    def __init__(
        self,
        model_name: str,
        *,
        dimension: int = 384,
        strict_mode: bool = False,
        max_consecutive_failures: int = 5,
        fallback_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Load a sentence-transformers model into process memory."""

        module = importlib.import_module("sentence_transformers")
        sentence_transformer = getattr(module, "SentenceTransformer")
        self._model = sentence_transformer(model_name)
        self.dimension = dimension
        self._strict_mode = strict_mode
        self._fallback_provider = fallback_provider or HashEmbeddingProvider(
            dimension=dimension
        )
        self._health = ProviderHealth(
            name="embedding",
            backend="sentence_transformers",
            max_consecutive_failures=max_consecutive_failures,
        )

    def _encode_many_sync(self, texts: list[str]) -> list[list[float]]:
        encoded = self._model.encode(texts, normalize_embeddings=True)
        if hasattr(encoded, "tolist"):
            raw = encoded.tolist()
        else:
            raw = encoded

        if texts and raw and isinstance(raw[0], (int, float)):
            raw = [raw]

        return [
            _normalize_vector([float(value) for value in vector], self.dimension)
            for vector in raw
        ]

    async def embed(self, text: str) -> list[float]:
        vectors = await self.embed_many([text])
        return vectors[0]

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            vectors = await asyncio.to_thread(self._encode_many_sync, list(texts))
            self._health.record_success()
            return vectors
        except (RuntimeError, ValueError, TypeError) as exc:
            self._health.record_failure(exc)
            if self._strict_mode and self._health.should_fail_fast():
                raise RuntimeError(
                    "sentence-transformers embedding provider entered fail-fast mode"
                ) from exc

            logger.warning(
                "Sentence-transformers embedding failed, using hash fallback for this batch: %s",
                exc,
            )
            return await self._fallback_provider.embed_many(texts)

    def health_snapshot(self) -> dict[str, Any]:
        return self._health.snapshot()

    async def aclose(self) -> None:
        return None


class LLMApiEmbeddingProvider:
    """Embedding provider that calls an OpenAI-compatible embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        embedding_url: str,
        model: str,
        timeout_seconds: float,
        dimension: int = 384,
        strict_mode: bool = False,
        max_consecutive_failures: int = 5,
        fallback_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Configure external embedding provider.

        Args:
            api_key: Provider API key.
            embedding_url: Embeddings endpoint URL.
            model: Embedding model name.
            timeout_seconds: HTTP timeout for embedding requests.
            dimension: Required output embedding dimension.
            fallback_provider: Local fallback used when API requests fail.
        """

        if not api_key.strip():
            raise ValueError("LLM_API_KEY must be set for llm_api embedding backend.")

        self._api_key = api_key
        self._embedding_url = embedding_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self.dimension = dimension
        self._strict_mode = strict_mode
        self._fallback_provider = fallback_provider or HashEmbeddingProvider(
            dimension=dimension
        )
        self._session = _build_retry_session()
        self._session_lock = threading.Lock()
        self._health = ProviderHealth(
            name="embedding",
            backend="llm_api",
            max_consecutive_failures=max_consecutive_failures,
        )

    def _request_embeddings_sync(self, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []

        analytics = PerfAnalytics(
            logger=logger,
            scope="llm_embedding_provider.request_embeddings_sync",
            context={"model": self._model, "input_count": len(inputs)},
        )

        try:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self._model,
                "input": inputs,
                "dimensions": self.dimension,
            }

            with analytics.stage("http_post", kind="network"):
                with self._session_lock:
                    response = self._session.post(
                        self._embedding_url,
                        headers=headers,
                        json=payload,
                        timeout=self._timeout_seconds,
                    )
                response.raise_for_status()

            with analytics.stage("parse_and_normalize_response", kind="compute"):
                data = response.json()
                items = data.get("data")
                if not isinstance(items, list):
                    raise ValueError("Embedding response is malformed: missing 'data' list.")

                by_index: dict[int, list[float]] = {}
                for item in items:
                    index = int(item.get("index", 0))
                    vector = item.get("embedding")
                    if not isinstance(vector, list):
                        raise ValueError("Embedding response is malformed: invalid vector payload.")
                    by_index[index] = _normalize_vector(
                        [float(value) for value in vector],
                        self.dimension,
                    )

                if len(by_index) != len(inputs):
                    raise ValueError("Embedding response size does not match request size.")

                return [by_index[index] for index in range(len(inputs))]
        finally:
            analytics.log_summary()

    async def embed(self, text: str) -> list[float]:
        vectors = await self.embed_many([text])
        return vectors[0]

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            vectors = await asyncio.to_thread(self._request_embeddings_sync, list(texts))
            self._health.record_success()
            return vectors
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            self._health.record_failure(exc)
            if self._strict_mode and self._health.should_fail_fast():
                raise RuntimeError("llm_api embedding provider entered fail-fast mode") from exc

            logger.warning(
                "LLM embedding request failed, using hash fallback for this batch: %s",
                exc,
            )
            return await self._fallback_provider.embed_many(texts)

    def health_snapshot(self) -> dict[str, Any]:
        return self._health.snapshot()

    async def aclose(self) -> None:
        await asyncio.to_thread(self._session.close)


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build embedding provider from runtime settings.

    If configured provider initialization fails, the function logs a warning
    and falls back to the deterministic hash-based provider.
    """

    backend = settings.embedding_backend.strip().lower()
    dimension = settings.embedding_dimension

    if backend == "llm_api":
        try:
            logger.info(
                "Using llm_api embeddings with model '%s' and endpoint '%s'",
                settings.llm_embedding_model,
                settings.llm_embedding_url,
            )
            return LLMApiEmbeddingProvider(
                api_key=settings.llm_api_key,
                embedding_url=settings.llm_embedding_url,
                model=settings.llm_embedding_model,
                timeout_seconds=settings.llm_embedding_timeout_seconds,
                dimension=dimension,
                strict_mode=settings.provider_strict_mode,
                max_consecutive_failures=settings.provider_max_consecutive_failures,
            )
        except (ValueError, TypeError) as exc:
            if settings.provider_strict_mode:
                raise RuntimeError(
                    "Failed to initialize llm_api embedding provider in strict mode."
                ) from exc
            logger.warning(
                "Falling back to hash embeddings. llm_api init failed: %s",
                exc,
            )
            return HashEmbeddingProvider(dimension=dimension)

    if backend == "sentence_transformers":
        try:
            logger.info(
                "Loading sentence-transformers model '%s'",
                settings.sentence_transformer_model,
            )
            return SentenceTransformerEmbeddingProvider(
                settings.sentence_transformer_model,
                dimension=dimension,
                strict_mode=settings.provider_strict_mode,
                max_consecutive_failures=settings.provider_max_consecutive_failures,
            )
        except (ImportError, AttributeError, ValueError, TypeError) as exc:
            if settings.provider_strict_mode:
                raise RuntimeError(
                    "Failed to initialize sentence-transformers embedding provider in strict mode."
                ) from exc
            logger.warning(
                "Falling back to hash embeddings. sentence-transformers init failed: %s",
                exc,
            )

    return HashEmbeddingProvider(dimension=dimension)
