"""
Structured JSON logging for the Club Management Suite backend.

Installs a pythonjsonlogger.JsonFormatter on the root logger and registers
Flask before/after request hooks to emit per-request log lines with fields:
    timestamp, level, name, message, request_id, method, path, status,
    duration_ms

Only activates when app.config['JSON_LOGGING'] is True (default).
Set JSON_LOGGING=False in TestingConfig to keep test output readable.
"""

from __future__ import annotations

import time
import logging
from uuid import uuid4

from flask import Flask, g, request


def configure_logging(app: Flask) -> None:
    """Attach JSON logging and request instrumentation to *app*."""
    if not app.config.get("JSON_LOGGING", True):
        return

    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import]
    except ImportError:
        app.logger.warning("python-json-logger not installed; JSON logging disabled")
        return

    class _RequestAwareFormatter(jsonlogger.JsonFormatter):
        """JsonFormatter that injects request_id from Flask's g when available."""

        def add_fields(
            self, log_record: dict, record: logging.LogRecord, message_dict: dict
        ) -> None:
            super().add_fields(log_record, record, message_dict)
            # Rename default fields to match our schema
            log_record["timestamp"] = (
                log_record.pop("asctime", None) or record.asctime
                if hasattr(record, "asctime")
                else None
            )
            log_record["level"] = log_record.pop("levelname", record.levelname)
            log_record["name"] = record.name
            # Inject request_id when inside a request context
            try:
                log_record["request_id"] = getattr(g, "request_id", None)
            except RuntimeError:
                log_record["request_id"] = None

    handler = logging.StreamHandler()
    handler.setFormatter(
        _RequestAwareFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate output
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Silence Werkzeug's default request line — we log our own
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @app.before_request
    def _assign_request_id() -> None:
        g.request_id = uuid4().hex[:8]
        g._request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = int(
            (time.monotonic() - getattr(g, "_request_start", time.monotonic())) * 1000
        )
        app.logger.info(
            "request",
            extra={
                "request_id": getattr(g, "request_id", None),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
