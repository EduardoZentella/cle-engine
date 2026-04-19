"""Health and degradation tracking for external providers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ProviderHealth:
    """Tracks provider reliability and degradation state.

    The state is updated by providers whenever remote or local model calls
    succeed/fail so endpoints can expose explicit degradation telemetry.
    """

    name: str
    backend: str
    max_consecutive_failures: int
    degraded: bool = False
    total_failures: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    last_failure_at: str | None = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.degraded = False

    def record_failure(self, exc: Exception) -> None:
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_error = str(exc)
        self.last_failure_at = datetime.now(tz=timezone.utc).isoformat()
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.degraded = True

    def should_fail_fast(self) -> bool:
        return self.consecutive_failures >= self.max_consecutive_failures

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)
