"""Infrastructure health checks for periodic monitoring.

Provides Celery tasks for disk, Redis, and PostgreSQL health monitoring.
"""

import logging
import os
import time

from vollbuild.extensions import db
from vollbuild.core.services.alerts import alert_error, alert_resolved
from vollbuild.core.tasks import celery_app

_log = logging.getLogger(__name__)

# Track alert state to avoid repeated alerts
_alert_states: dict[str, bool] = {}


def check_disk_space(threshold_pct: float = 85.0) -> dict:
    """Check disk usage and alert if above threshold.

    Returns a status dict with the check result.
    """
    try:
        usage = _get_disk_usage()
        if usage is None:
            return {"status": "skipped", "reason": "unable_to_determine"}

        if usage > threshold_pct:
            if not _alert_states.get("disk_space"):
                alert_error(
                    title="High Disk Usage",
                    description=f"Disk usage at {usage:.1f}% (threshold: {threshold_pct}%)",
                    fields=[
                        {"name": "Usage", "value": f"{usage:.1f}%", "inline": True},
                        {
                            "name": "Threshold",
                            "value": f"{threshold_pct}%",
                            "inline": True,
                        },
                    ],
                )
                _alert_states["disk_space"] = True
            return {"status": "alert", "usage_pct": usage, "threshold": threshold_pct}

        # Resolved
        if _alert_states.get("disk_space"):
            alert_resolved(
                title="Disk Usage Resolved",
                description=f"Disk usage back to {usage:.1f}%",
            )
            _alert_states["disk_space"] = False

        return {"status": "ok", "usage_pct": usage}
    except Exception:
        _log.debug("Failed to check disk space", exc_info=True)
        return {"status": "error", "reason": "check_failed"}


def check_redis_health() -> dict:
    """Check Redis connectivity and alert if down.

    Returns a status dict with the check result.
    """
    try:
        from vollbuild.api.metrics import _get_redis_client

        client = _get_redis_client()
        if client is None:
            if not _alert_states.get("redis"):
                alert_error(
                    title="Redis Unavailable",
                    description="Redis client could not be initialized",
                )
                _alert_states["redis"] = True
            return {"status": "alert", "reason": "client_unavailable"}

        start = time.time()
        client.ping()
        latency_ms = (time.time() - start) * 1000

        if _alert_states.get("redis"):
            alert_resolved(
                title="Redis Recovered",
                description=f"Redis responding normally ({latency_ms:.1f}ms)",
            )
            _alert_states["redis"] = False

        return {"status": "ok", "latency_ms": round(latency_ms, 1)}
    except Exception:
        if not _alert_states.get("redis"):
            alert_error(
                title="Redis Connection Failed",
                description="Redis ping failed with an exception",
            )
            _alert_states["redis"] = True
        return {"status": "error", "reason": "ping_failed"}


def check_postgres_health() -> dict:
    """Check PostgreSQL connectivity and alert if down.

    Returns a status dict with the check result.
    """
    try:
        from sqlalchemy import text

        start = time.time()
        db.session.execute(text("SELECT 1"))
        latency_ms = (time.time() - start) * 1000

        if _alert_states.get("postgres"):
            alert_resolved(
                title="PostgreSQL Recovered",
                description=f"Database responding normally ({latency_ms:.1f}ms)",
            )
            _alert_states["postgres"] = False

        return {"status": "ok", "latency_ms": round(latency_ms, 1)}
    except Exception:
        if not _alert_states.get("postgres"):
            alert_error(
                title="PostgreSQL Connection Failed",
                description="Database health check failed",
            )
            _alert_states["postgres"] = True
        return {"status": "error", "reason": "connection_failed"}


def run_all_checks() -> dict:
    """Run all infrastructure checks and return aggregated status."""
    results = {
        "disk": check_disk_space(),
        "redis": check_redis_health(),
        "postgres": check_postgres_health(),
    }

    has_alert = any(r["status"] == "alert" for r in results.values())
    results["overall"] = "alert" if has_alert else "ok"
    return results


def _get_disk_usage() -> float | None:
    """Get disk usage percentage for the current working directory."""
    try:
        # Use os.statvfs on Unix, fallback to shutil on Windows
        if os.name == "nt":
            import shutil

            total, used, free = shutil.disk_usage(".")
            return (used / total) * 100
        else:
            stat = os.statvfs(".")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            return (used / total) * 100
    except Exception:
        return None


@celery_app.task(name="vollbuild.core.tasks.infra_checks.run_all_checks_task")
def run_all_checks_task() -> None:
    """Celery task wrapper for run_all_checks."""
    result = run_all_checks()
    _log.info("Infrastructure checks: %s", result)
