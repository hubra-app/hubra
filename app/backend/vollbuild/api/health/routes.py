"""Health blueprint — liveness and readiness endpoints."""

from __future__ import annotations

import time

from flask import Blueprint, jsonify

from vollbuild.api.health.cache import HealthCache
from vollbuild.api.health.services import HealthService
from vollbuild.api.permissions import require_admin
from vollbuild.api.version.service import VersionService
from vollbuild.extensions import limiter

health_bp = Blueprint("health", __name__)

_STALE_THRESHOLD = 60  # seconds — 3× the 20s beat interval


@health_bp.get("/health")
@limiter.exempt
def health_check():
    """Minimal liveness check for load balancers — no auth, no infra details.

    Reads the cached status populated by the ``run_health_checks`` Celery beat
    task (every 20s).  On cache miss or staleness returns ``degraded`` with
    HTTP 200 so load balancers do not flap when the task is briefly delayed.
    """
    cached = HealthCache.get()
    if cached is None:
        return jsonify({"status": "degraded"}), 200

    overall = cached.get("status", "degraded")
    http_status = 200 if overall in ("ok", "degraded") else 503
    return jsonify({"status": overall}), http_status


@health_bp.get("/health/detailed")
@require_admin
@limiter.exempt
def health_check_detailed():
    """Full health breakdown including service URLs and latencies — admin only.

    Runs all checks concurrently (wall time ≈ slowest check) so admins see
    current latencies rather than a cached snapshot.  Includes a ``stale``
    flag derived from the cached ``checked_at`` to surface a dead beat task.
    """
    payload = HealthService.run_all_checks()
    payload["version"] = VersionService.get_version()

    cached = HealthCache.get()
    if cached is not None and "checked_at" in cached:
        age = time.time() - cached["checked_at"]
        payload["stale"] = age > _STALE_THRESHOLD
        payload["checked_at"] = cached["checked_at"]
    else:
        payload["stale"] = True

    http_status = 200 if payload["status"] in ("ok", "degraded") else 503
    return jsonify(payload), http_status
