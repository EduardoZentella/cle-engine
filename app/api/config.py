"""Runtime configuration for the CLE Engine backend.

This module centralizes environment-variable parsing and exposes a typed
`Settings` object consumed by application startup.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_EMBEDDING_DIMENSION = 384


def _read_int(name: str, default: int) -> int:
    """Read an integer environment variable with safe fallback behavior.

    Returns `default` when the variable is missing or cannot be parsed as an
    integer.
    """

    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _read_float(name: str, default: float) -> float:
    """Read a float environment variable with safe fallback behavior.

    Returns `default` when the variable is missing or cannot be parsed as a
    float.
    """

    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable with safe fallback behavior."""

    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def read_embedding_dimension_from_env() -> int:
    """Read embedding dimension from environment with project default fallback."""

    return _read_int("EMBEDDING_DIMENSION", DEFAULT_EMBEDDING_DIMENSION)


@dataclass(frozen=True, slots=True)
class Settings:
    """Typed runtime settings loaded from process environment variables.

    The values here configure database connectivity, retrieval parameters, and
    embedding provider behavior.
    """

    database_url: str
    db_pool_min_size: int
    db_pool_max_size: int
    embedding_backend: str
    embedding_dimension: int
    sentence_transformer_model: str
    llm_api_key: str
    llm_embedding_model: str
    llm_embedding_url: str
    llm_embedding_timeout_seconds: float
    intelligence_backend: str
    llm_completion_model: str
    llm_completion_url: str
    llm_completion_timeout_seconds: float
    relevance_approval_threshold: float
    relevance_regenerate_threshold: float
    retrieval_vector_k: int
    retrieval_lexical_k: int
    retrieval_final_k: int
    retrieval_rrf_k: int
    vector_confidence_threshold: float
    provider_strict_mode: bool
    provider_max_consecutive_failures: int
    final_reranker_model_dir: str
    final_reranker_manifest_file: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Construct settings from environment variables.

        Defaults are intentionally development-friendly so local execution works
        without a fully populated environment.
        """

        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://admin:local_dev@localhost:5432/cle_engine",
            ),
            db_pool_min_size=_read_int("DB_POOL_MIN_SIZE", 1),
            db_pool_max_size=_read_int("DB_POOL_MAX_SIZE", 10),
            embedding_backend=os.getenv("EMBEDDING_BACKEND", "hash"),
            embedding_dimension=read_embedding_dimension_from_env(),
            sentence_transformer_model=os.getenv(
                "SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"
            ),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_embedding_model=os.getenv(
                "LLM_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            llm_embedding_url=os.getenv(
                "LLM_EMBEDDING_URL", "https://api.openai.com/v1/embeddings"
            ),
            llm_embedding_timeout_seconds=_read_float(
                "LLM_EMBEDDING_TIMEOUT_SECONDS", 15.0
            ),
            intelligence_backend=os.getenv("INTELLIGENCE_BACKEND", "heuristic"),
            llm_completion_model=os.getenv("LLM_COMPLETION_MODEL", "default-model"),
            llm_completion_url=os.getenv(
                "LLM_COMPLETION_URL", "https://api.openai.com/v1/chat/completions"
            ),
            llm_completion_timeout_seconds=_read_float(
                "LLM_COMPLETION_TIMEOUT_SECONDS", 20.0
            ),
            relevance_approval_threshold=_read_float(
                "RELEVANCE_APPROVAL_THRESHOLD", 0.55
            ),
            relevance_regenerate_threshold=_read_float(
                "RELEVANCE_REGENERATE_THRESHOLD", 0.45
            ),
            retrieval_vector_k=_read_int("RETRIEVAL_VECTOR_K", 20),
            retrieval_lexical_k=_read_int("RETRIEVAL_LEXICAL_K", 20),
            retrieval_final_k=_read_int("RETRIEVAL_FINAL_K", 8),
            retrieval_rrf_k=_read_int("RETRIEVAL_RRF_K", 60),
            vector_confidence_threshold=_read_float("VECTOR_CONFIDENCE_THRESHOLD", 0.33),
            provider_strict_mode=_read_bool("PROVIDER_STRICT_MODE", False),
            provider_max_consecutive_failures=_read_int(
                "PROVIDER_MAX_CONSECUTIVE_FAILURES", 5
            ),
            final_reranker_model_dir=os.getenv(
                "FINAL_RERANKER_MODEL_DIR", "models/final_reranker"
            ),
            final_reranker_manifest_file=os.getenv(
                "FINAL_RERANKER_MANIFEST_FILE", "manifest.json"
            ),
        )