"""Reusable runtime performance analytics helpers.

These helpers emit structured logs for wall time, CPU time, wait time, and
memory deltas to help identify likely bottlenecks in request pipelines.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import sys
import time
import tracemalloc
from typing import Any, Iterator

try:  # pragma: no cover - platform dependent
    import resource
except ImportError:  # pragma: no cover - platform dependent
    resource = None


MIN_WALL_MS_FOR_CLASSIFICATION = 25.0
MEMORY_PRESSURE_THRESHOLD_KB = 50_000.0


def _ensure_tracemalloc_started() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start(25)


def _rss_megabytes() -> float | None:
    if resource is None:  # pragma: no cover - platform dependent
        return None

    try:  # pragma: no cover - platform dependent
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return float(usage) / (1024.0 * 1024.0)
        return float(usage) / 1024.0
    except Exception:
        return None


def _classify_bottleneck(
    *,
    kind: str,
    wall_ms: float,
    cpu_ms: float,
    wait_ms: float,
    mem_delta_kb: float,
) -> str:
    if wall_ms < MIN_WALL_MS_FOR_CLASSIFICATION:
        return "too_fast_to_classify"

    if mem_delta_kb >= MEMORY_PRESSURE_THRESHOLD_KB:
        return "memory_pressure"

    if kind in {"network", "database", "io"} and wait_ms > cpu_ms * 2.5:
        return "connection_or_io_wait"

    if kind in {"compute", "cpu"} and cpu_ms > wall_ms * 0.65:
        return "compute_cpu_bound"

    if wait_ms > cpu_ms * 2.0:
        return "io_wait"

    return "balanced"


@dataclass(frozen=True, slots=True)
class StageAnalytics:
    """Captured analytics for a single stage."""

    name: str
    kind: str
    wall_ms: float
    cpu_ms: float
    wait_ms: float
    mem_delta_kb: float
    rss_delta_mb: float | None
    bottleneck: str


class PerfAnalytics:
    """Collect and emit structured stage analytics to logging."""

    def __init__(
        self,
        *,
        logger: logging.Logger,
        scope: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self._logger = logger
        self._scope = scope
        self._context = context or {}
        self._stages: list[StageAnalytics] = []
        self._started_at = time.perf_counter()

    @contextmanager
    def stage(self, name: str, *, kind: str = "compute") -> Iterator[None]:
        """Measure and log a named stage."""

        _ensure_tracemalloc_started()
        wall_started = time.perf_counter()
        cpu_started = time.process_time()
        rss_started = _rss_megabytes()

        mem_started = 0
        if tracemalloc.is_tracing():
            mem_started, _ = tracemalloc.get_traced_memory()

        try:
            yield
        finally:
            wall_ms = (time.perf_counter() - wall_started) * 1000.0
            cpu_ms = (time.process_time() - cpu_started) * 1000.0
            wait_ms = max(0.0, wall_ms - cpu_ms)

            mem_delta_kb = 0.0
            if tracemalloc.is_tracing():
                mem_current, _ = tracemalloc.get_traced_memory()
                mem_delta_kb = (mem_current - mem_started) / 1024.0

            rss_ended = _rss_megabytes()
            rss_delta_mb: float | None
            if rss_started is None or rss_ended is None:
                rss_delta_mb = None
            else:
                rss_delta_mb = rss_ended - rss_started

            bottleneck = _classify_bottleneck(
                kind=kind,
                wall_ms=wall_ms,
                cpu_ms=cpu_ms,
                wait_ms=wait_ms,
                mem_delta_kb=mem_delta_kb,
            )
            stage = StageAnalytics(
                name=name,
                kind=kind,
                wall_ms=wall_ms,
                cpu_ms=cpu_ms,
                wait_ms=wait_ms,
                mem_delta_kb=mem_delta_kb,
                rss_delta_mb=rss_delta_mb,
                bottleneck=bottleneck,
            )
            self._stages.append(stage)

            rss_text = "na"
            if rss_delta_mb is not None:
                rss_text = f"{rss_delta_mb:.2f}"

            self._logger.warning(
                "perf_analytics scope=%s stage=%s kind=%s wall_ms=%.2f cpu_ms=%.2f "
                "wait_ms=%.2f mem_delta_kb=%.2f rss_delta_mb=%s bottleneck=%s context=%s",
                self._scope,
                stage.name,
                stage.kind,
                stage.wall_ms,
                stage.cpu_ms,
                stage.wait_ms,
                stage.mem_delta_kb,
                rss_text,
                stage.bottleneck,
                self._context,
            )

    def log_summary(self) -> None:
        """Emit summary analytics for all captured stages."""

        if not self._stages:
            return

        total_wall_ms = (time.perf_counter() - self._started_at) * 1000.0
        total_cpu_ms = sum(stage.cpu_ms for stage in self._stages)
        total_wait_ms = max(0.0, total_wall_ms - total_cpu_ms)
        longest = max(self._stages, key=lambda stage: stage.wall_ms)

        self._logger.warning(
            "perf_analytics scope=%s summary total_ms=%.2f total_cpu_ms=%.2f "
            "total_wait_ms=%.2f stages=%d longest_stage=%s longest_ms=%.2f context=%s",
            self._scope,
            total_wall_ms,
            total_cpu_ms,
            total_wait_ms,
            len(self._stages),
            longest.name,
            longest.wall_ms,
            self._context,
        )
