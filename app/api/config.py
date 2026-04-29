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

    The values here configure database connectivity, Gemini API, and
    embedding dimensions for the 7-stage linear pipeline.
    """

    database_url: str
    db_pool_min_size: int
    db_pool_max_size: int
    gemini_api_key: str
    embedding_dimension: int

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
            gemini_api_key=(
                os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("LLM_API_KEY")
                or ""
            ),
            embedding_dimension=read_embedding_dimension_from_env(),
        )