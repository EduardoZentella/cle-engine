"""Debug logging system for troubleshooting."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DebugLogger:
    """Structured debug logging for pipeline events."""

    def __init__(self):
        """Initialize debug logger."""
        pass

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
            "[%s] %s (stage=%s, user=%s, context=%s)",
            level.upper(),
            message,
            stage,
            user_id,
            json.dumps(context or {}),
        )
