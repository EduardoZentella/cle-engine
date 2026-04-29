"""Performance metrics and debug logging infrastructure."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from psycopg2.extras import RealDictCursor

from app.api.db import DatabasePool

logger = logging.getLogger(__name__)


class MetricStatus(str, Enum):
    """Metric status values."""

    SUCCESS = "success"
    ERROR = "error"
    RETRY = "retry"
    TIMEOUT = "timeout"


@dataclass
class PerformanceMetric:
    """Single performance metric record."""

    stage: str  # "embed", "translate", "retrieve", "generate", "evaluate"
    duration_ms: float
    status: MetricStatus
    user_id: str | None = None
    attempt: int | None = None
    metadata: dict[str, Any] | None = None
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage."""
        data = asdict(self)
        data["status"] = self.status.value
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        return data


class PerformanceTracker:
    """Track and store performance metrics."""

    def __init__(self, database: DatabasePool | None = None):
        """Initialize tracker with optional database persistence."""
        self.database = database
        self.metrics: list[PerformanceMetric] = []

    def record(
        self,
        stage: str,
        duration_ms: float,
        status: MetricStatus,
        user_id: str | None = None,
        attempt: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a performance metric.

        Args:
            stage: Pipeline stage name
            duration_ms: Time taken in milliseconds
            status: Success/error/retry/timeout
            user_id: User ID if applicable
            attempt: Retry attempt number
            metadata: Additional context
        """
        metric = PerformanceMetric(
            stage=stage,
            duration_ms=duration_ms,
            status=status,
            user_id=user_id,
            attempt=attempt,
            metadata=metadata,
            timestamp=datetime.utcnow(),
        )

        self.metrics.append(metric)

        # Log immediately
        level = logging.WARNING if status != MetricStatus.SUCCESS else logging.DEBUG
        logger.log(
            level,
            "[perf] %s status=%s duration_ms=%.2f user_id=%s attempt=%s",
            stage,
            status.value,
            duration_ms,
            user_id,
            attempt,
        )

        # Persist to DB if available
        if self.database:
            self._persist_metric(metric)

    def _persist_metric(self, metric: PerformanceMetric) -> None:
        """Persist metric to database (non-blocking)."""
        try:
            with self.database.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO performance_metrics
                        (stage, duration_ms, status, user_id, attempt, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            metric.stage,
                            metric.duration_ms,
                            metric.status.value,
                            metric.user_id,
                            metric.attempt,
                            json.dumps(metric.metadata or {}),
                            metric.timestamp,
                        ),
                    )
        except Exception as err:
            logger.error("Failed to persist metric: %s", err)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of recorded metrics."""
        if not self.metrics:
            return {}

        by_stage: dict[str, list[float]] = {}
        error_count = 0

        for metric in self.metrics:
            if metric.stage not in by_stage:
                by_stage[metric.stage] = []

            by_stage[metric.stage].append(metric.duration_ms)

            if metric.status != MetricStatus.SUCCESS:
                error_count += 1

        summary = {}
        for stage, durations in by_stage.items():
            summary[stage] = {
                "count": len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "avg_ms": sum(durations) / len(durations),
            }

        summary["_total"] = {
            "total_duration_ms": sum(d for stage_durations in by_stage.values() for d in stage_durations),
            "error_count": error_count,
            "error_rate": error_count / len(self.metrics),
        }

        return summary


class DebugLogger:
    """Structured debug logging for pipeline events."""

    def __init__(self, database: DatabasePool | None = None):
        """Initialize debug logger."""
        self.database = database

    def log_event(
        self,
        level: str,
        message: str,
        user_id: str | None = None,
        stage: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log a debug event.

        Args:
            level: "debug", "info", "warning", "error"
            message: Log message
            user_id: User context
            stage: Pipeline stage
            context: Additional context dict
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "user_id": user_id,
            "stage": stage,
            "context": context,
        }

        # Log to Python logger
        log_func = getattr(logger, level, logger.info)
        log_func(
            "[debug] %s stage=%s user_id=%s context=%s",
            message,
            stage,
            user_id,
            json.dumps(context or {}),
        )

        # Persist to DB if available
        if self.database:
            self._persist_log(log_entry)

    def _persist_log(self, log_entry: dict[str, Any]) -> None:
        """Persist log to database (non-blocking)."""
        try:
            with self.database.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO debug_logs
                        (level, message, user_id, stage, context, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            log_entry["level"],
                            log_entry["message"],
                            log_entry["user_id"],
                            log_entry["stage"],
                            json.dumps(log_entry["context"] or {}),
                            log_entry["timestamp"],
                        ),
                    )
        except Exception as err:
            logger.error("Failed to persist debug log: %s", err)
