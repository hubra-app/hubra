"""Celery task failure monitoring and API error rate alerting.

Provides:
- task_failure_alert: Celery signal handler that fires on task failure
- check_api_error_rate_task: Periodic Celery task that checks error rates
- check_api_error_rate: Core logic (importable without Celery)
"""

import logging
import time
from datetime import datetime, timezone

from celery import signals

from hubra.core.services.alerts import alert_error
from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)

# Track recent failures for rate calculation
_failure_counts: dict[str, list[float]] = {}
_alert_cooldowns: dict[str, float] = {}
_COOLDOWN_SECONDS = 3600  # 1 hour between repeated alerts for same task


@signals.task_failure.connect
def task_failure_alert(
    sender,
    task_id,
    exception,
    args,
    kwargs,
    traceback,
    **kw,
):
    """Send Discord alert when a Celery task fails."""
    task_name = sender.name if hasattr(sender, "name") else str(sender)

    # Track failure
    now = time.time()
    _failure_counts.setdefault(task_name, []).append(now)
    # Prune old entries (keep last hour)
    _failure_counts[task_name] = [
        t for t in _failure_counts[task_name] if now - t < 3600
    ]

    # Check cooldown
    last_alert = _alert_cooldowns.get(task_name, 0)
    if now - last_alert < _COOLDOWN_SECONDS:
        _log.debug("Skipping alert for %s (cooldown)", task_name)
        return

    failure_count = len(_failure_counts[task_name])
    alert_error(
        title=f"Task Failed: {task_name}",
        description=f"Task `{task_name}` raised an exception.",
        fields=[
            {"name": "Task ID", "value": str(task_id)[:100], "inline": True},
            {"name": "Failures (1h)", "value": str(failure_count), "inline": True},
            {"name": "Exception", "value": str(exception)[:500], "inline": False},
        ],
    )
    _alert_cooldowns[task_name] = now


def check_api_error_rate() -> dict:
    """Check API error rate from Redis counters and alert if threshold exceeded.

    Returns a status dict with the check result.
    """
    try:
        from flask import current_app

        threshold = current_app.config.get("API_ERROR_RATE_THRESHOLD", 0.1)
    except RuntimeError:
        threshold = 0.1

    try:
        from hubra.api.metrics import _get_redis_client

        client = _get_redis_client()
        if client is None:
            return {"status": "skipped", "reason": "redis_unavailable"}

        now = datetime.now(timezone.utc)
        key_total = f"api:errors:total:{now.strftime('%Y-%m')}"
        key_errors = f"api:errors:count:{now.strftime('%Y-%m')}"

        total = int(client.get(key_total) or 0)
        errors = int(client.get(key_errors) or 0)

        if total == 0:
            return {"status": "ok", "total": 0, "errors": 0, "rate": 0}

        rate = errors / total
        if rate > threshold:
            alert_error(
                title="High API Error Rate",
                description=f"Error rate {rate:.1%} exceeds threshold {threshold:.1%}",
                fields=[
                    {"name": "Total Requests", "value": str(total), "inline": True},
                    {"name": "Errors", "value": str(errors), "inline": True},
                    {"name": "Rate", "value": f"{rate:.1%}", "inline": True},
                ],
            )
            return {"status": "alert", "total": total, "errors": errors, "rate": rate}

        return {"status": "ok", "total": total, "errors": errors, "rate": rate}
    except Exception:
        _log.debug("Failed to check API error rate", exc_info=True)
        return {"status": "error", "reason": "check_failed"}


@celery_app.task(name="hubra.core.tasks.monitoring.check_api_error_rate_task")
def check_api_error_rate_task() -> None:
    """Celery task wrapper for check_api_error_rate."""
    result = check_api_error_rate()
    _log.info("API error rate check: %s", result)
