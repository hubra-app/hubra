"""Health blueprint — liveness and readiness endpoints."""

from __future__ import annotations


from flask import Blueprint, jsonify

from hubra.api.health.cache import HealthCache
from hubra.core.extensions import limiter

health_bp = Blueprint("health", __name__)


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
