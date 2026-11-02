"""Celery task failure monitoring and API error rate alerting.

Provides:
- task_failure_alert: Celery signal handler that fires on task failure
- check_api_error_rate_task: Periodic Celery task that checks error rates
- check_api_error_rate: Core logic (importable without Celery)
"""

import logging
import time

from celery import signals

from hubra.core.services.alerts import alert_error, alert_resolved
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


# The error-rate alert: server errors (5xx) in the last hour, from the
# request timing in ``perf_monitor``.  4xx answers are not errors here: an
# expired sign-in (401) after a release, a 404 or a refused form are normal.
MIN_REQUESTS_FOR_ALERT = 50
_ALERT_STATE_KEY = "monitor:api_errors:alerting"
_alerting_local = {"on": False}


def _alert_state(client) -> bool:
    if client is None:
        return _alerting_local["on"]
    try:
        return bool(client.get(_ALERT_STATE_KEY))
    except Exception:  # noqa: BLE001
        return _alerting_local["on"]


def _set_alert_state(client, on: bool) -> None:
    _alerting_local["on"] = on
    if client is None:
        return
    try:
        if on:
            client.set(_ALERT_STATE_KEY, "1", ex=7 * 24 * 3600)
        else:
            client.delete(_ALERT_STATE_KEY)
    except Exception:  # noqa: BLE001
        pass


def check_api_error_rate() -> dict:
    """Alert when too many API requests failed with a server error.

    Looks at the last hour (``perf_monitor.last_hour``): at least
    ``MIN_REQUESTS_FOR_ALERT`` requests and a 5xx share above
    ``API_ERROR_RATE_THRESHOLD`` (5 % by default).  Errors while a release
    starts up are counted apart (``perf_monitor.WARMUP_SECONDS``) and
    maintenance answers not at all.  One alert per incident: it goes out when
    the rate gets too high and again, as resolved, when it is back down.
    Paused while the platform is in maintenance.
    """
    from hubra.core.services import maintenance, perf_monitor

    try:
        from flask import current_app

        threshold = float(
            current_app.config.get(
                "API_ERROR_RATE_THRESHOLD", perf_monitor.SERVER_ERROR_SHARE
            )
        )
    except RuntimeError:
        threshold = perf_monitor.SERVER_ERROR_SHARE

    try:
        if maintenance.is_active():
            return {"status": "maintenance"}
        last = perf_monitor.last_hour()
        total = int(last["requests"] or 0)
        errors = int(last["status"].get("5xx", 0))
        rate = errors / total if total else 0.0
        client = perf_monitor._redis()
        alerting = _alert_state(client)
        result = {"total": total, "errors": errors, "rate": rate}

        if total < MIN_REQUESTS_FOR_ALERT:
            return {"status": "ok", "reason": "too_few_requests", **result}
        if rate > threshold:
            if alerting:
                return {"status": "still_high", **result}
            alert_error(
                title="High API Error Rate",
                description=(
                    f"{rate:.1%} of API requests in the last hour failed with a "
                    f"server error (threshold {threshold:.1%})"
                ),
                fields=[
                    {"name": "Requests", "value": str(total), "inline": True},
                    {"name": "Server errors", "value": str(errors), "inline": True},
                    {"name": "Rate", "value": f"{rate:.1%}", "inline": True},
                ],
            )
            _set_alert_state(client, True)
            return {"status": "alert", **result}
        if alerting:
            alert_resolved(
                title="API Error Rate Back to Normal",
                description=f"{rate:.1%} server errors in the last hour",
            )
            _set_alert_state(client, False)
            return {"status": "resolved", **result}
        return {"status": "ok", **result}
    except Exception:
        _log.debug("Failed to check API error rate", exc_info=True)
        return {"status": "error", "reason": "check_failed"}


@celery_app.task(name="hubra.core.tasks.monitoring.check_api_error_rate_task")
def check_api_error_rate_task() -> None:
    """Celery task wrapper for check_api_error_rate."""
    result = check_api_error_rate()
    _log.info("API error rate check: %s", result)
