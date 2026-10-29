"""Health service — liveness/readiness checks for DB, Redis, and mail services."""

from __future__ import annotations

import imaplib
import logging
import smtplib
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

from flask import current_app

_logger = logging.getLogger(__name__)

_smtp_context = ssl.create_default_context()
_smtp_context.check_hostname = False
_smtp_context.verify_mode = ssl.CERT_NONE

_CHECK_TIMEOUT = 1.0  # seconds per individual check


def _imap_client(host: str, port: int) -> imaplib.IMAP4:
    """Port 993 is IMAP over TLS from the first byte (as 465 is for SMTP);
    a plain client there waits for a greeting that never comes."""
    if port == 993:
        return imaplib.IMAP4_SSL(host, port, timeout=1)
    return imaplib.IMAP4(host, port, timeout=1)


class HealthService:
    """Per-service health checks."""

    @staticmethod
    def run_all_checks(timeout: float = _CHECK_TIMEOUT) -> dict:
        """Run every ``check_*`` method concurrently and return the full payload.

        Each check is capped at *timeout* seconds (wall time).  A check that
        exceeds it returns ``{"ok": False, "error": "timeout"}`` so a single
        black-hole host cannot stall the whole health probe.

        Returns the same payload shape ``_run_checks`` previously produced::
            {"status": ..., "services": {db, redis, smtp, imap}}
        """
        from flask import current_app

        app = current_app._get_current_object()  # type: ignore[attr-defined]

        checks: dict[str, Callable[[], dict]] = {
            "db": HealthService.check_db,
            "redis": HealthService.check_redis,
            "smtp": HealthService.check_smtp,
            "imap": HealthService.check_imap,
        }

        def _run_with_context(fn: Callable[[], dict]) -> dict:
            with app.app_context():
                return fn()

        services: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=len(checks)) as pool:
            futures = {
                name: pool.submit(_run_with_context, fn) for name, fn in checks.items()
            }
            for name, fut in futures.items():
                start = time.monotonic()
                try:
                    services[name] = fut.result(timeout=timeout)
                except FuturesTimeout:
                    services[name] = {
                        "ok": False,
                        "latency_ms": int((time.monotonic() - start) * 1000),
                        "error": "timeout",
                    }
                    fut.cancel()
                except Exception as exc:  # pragma: no cover — defensive
                    services[name] = {
                        "ok": False,
                        "latency_ms": int((time.monotonic() - start) * 1000),
                        "error": str(exc),
                    }

        critical_ok = services["db"]["ok"] and services["redis"]["ok"]

        from hubra.core.modules import is_enabled

        if is_enabled("mail"):
            mail_ok = services["smtp"]["ok"] and services["imap"]["ok"]
        else:
            mail_ok = True

        if critical_ok and mail_ok:
            overall = "ok"
        elif critical_ok:
            overall = "degraded"
        else:
            overall = "error"

        return {"status": overall, "services": services}

    @staticmethod
    def check_db() -> dict:
        """Check database connectivity."""
        start = time.monotonic()
        ok = False
        error = None
        try:
            from hubra.core.extensions import db

            db.session.execute(db.text("SELECT 1"))
            ok = True
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)
        result: dict = {"ok": ok, "latency_ms": latency_ms}
        if error:
            result["error"] = error
        return result

    @staticmethod
    def check_redis() -> dict:
        """Check Redis connectivity."""
        start = time.monotonic()
        ok = False
        error = None
        try:
            import redis as redis_lib

            url = current_app.config.get("REDIS_URL", "")
            if not url or url == "memory://":
                return {
                    "ok": False,
                    "latency_ms": 0,
                    "error": "REDIS_URL not configured",
                }
            client = redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            ok = True
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)
        result: dict = {"ok": ok, "latency_ms": latency_ms}
        if error:
            result["error"] = error
        return result

    @staticmethod
    def check_smtp() -> dict:
        """Check the platform mail relay (manager portal, defaults from env)."""
        from hubra.core.services import platform_settings

        start = time.monotonic()
        ok = False
        error = None
        try:
            relay = platform_settings.relay()
            smtp_host = relay.host
            smtp_port = relay.port
            if not smtp_host:
                return {
                    "ok": False,
                    "latency_ms": 0,
                    "error": "Mail relay not configured",
                }

            with smtplib.SMTP(smtp_host, smtp_port, timeout=1) as server:
                server.ehlo()
                if smtp_port != 25:
                    server.starttls(context=_smtp_context)
                    server.ehlo()
                ok = True
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)
        result: dict = {"ok": ok, "latency_ms": latency_ms}
        if error:
            result["error"] = error
        return result

    @staticmethod
    def check_imap() -> dict:
        """Check Infomaniak IMAP connectivity."""
        start = time.monotonic()
        ok = False
        error = None
        try:
            imap_host = current_app.config.get("IMAP_HOST", "")
            imap_port = int(current_app.config.get("IMAP_PORT", 993))
            if not imap_host:
                return {
                    "ok": False,
                    "latency_ms": 0,
                    "error": "IMAP_HOST not configured",
                }

            with _imap_client(imap_host, imap_port) as client:
                ok = client.capabilities is not None
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)
        result: dict = {"ok": ok, "latency_ms": latency_ms}
        if error:
            result["error"] = error
        return result
