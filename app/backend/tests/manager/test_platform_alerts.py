"""Platform alerts beyond mail: service outages, failed backups, plugin news,
and the open-problems overview in manage › Platform › Alerts."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import email, platform_monitor, platform_settings

BASE = "/api/v1/manager/platform"


@pytest.fixture
def staff(seeded_db, db):
    seeded_db["user"].is_superadmin = True
    platform_settings.set_many(
        {
            "mail.relay.host": "mail.example",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()
    return seeded_db["user"]


@pytest.fixture
def deliver():
    with patch.object(email, "_deliver") as d:
        yield d


def _alert_mails(deliver):
    """(subject, text body) of each alert mail handed to the relay."""
    from email import message_from_string

    out = []
    for c in deliver.call_args_list:
        msg = message_from_string(c.args[3])
        if not str(msg["Subject"]).startswith("[Hubra]"):
            continue
        text = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
        out.append((str(msg["Subject"]), text.get_payload(decode=True).decode()))
    return out


def _events(db, **filters):
    return db.session.query(PlatformEvent).filter_by(**filters).all()


def _health(db_ok=True, error="connection refused"):
    svc = {"ok": db_ok, "latency_ms": 1}
    if not db_ok:
        svc["error"] = error
    return {"services": {"db": svc, "redis": {"ok": True, "latency_ms": 1}}}


# ── Service outages ───────────────────────────────────────────────────────────


def test_database_outage_and_recovery(db, staff, deliver):
    previous = None
    for _ in range(platform_monitor.SERVICE_DOWN_AFTER - 1):
        previous = platform_monitor.watch_services(previous, _health(db_ok=False))
    assert _events(db, category="service") == []

    previous = platform_monitor.watch_services(previous, _health(db_ok=False))
    assert previous["watch"]["db"]["down_since"]
    (down,) = _events(db, kind="service.down")
    assert "connection refused" in down.message

    # Still down: nothing new.
    previous = platform_monitor.watch_services(previous, _health(db_ok=False))
    assert len(_events(db, kind="service.down")) == 1

    previous = platform_monitor.watch_services(previous, _health())
    assert previous["watch"]["db"] == {"fails": 0, "down_since": None}
    assert len(_events(db, kind="service.up")) == 1
    subjects = [subject for subject, _ in _alert_mails(deliver)]
    assert subjects == [
        "[Hubra] Database is unreachable",
        "[Hubra] Database is reachable again",
    ]


def test_imap_only_counts_with_the_mail_module(db, staff):
    payload = {"services": {"imap": {"ok": False, "error": "x"}}}
    with patch("hubra.core.modules.is_enabled", return_value=False):
        assert platform_monitor.watch_services(None, payload)["watch"] == {}


def test_health_task_carries_the_watch_over(db, staff):
    from hubra.core.tasks.health_tasks import run_health_checks

    with patch(
        "hubra.core.services.health.HealthService.run_all_checks",
        return_value={"status": "error", **_health(db_ok=False)},
    ):
        for _ in range(platform_monitor.SERVICE_DOWN_AFTER):
            payload = run_health_checks.run()
    assert payload["watch"]["db"]["fails"] == platform_monitor.SERVICE_DOWN_AFTER


# ── Backups and plugins ───────────────────────────────────────────────────────


def test_failed_scheduled_backups_alert(db, staff, deliver):
    records = [
        SimpleNamespace(status="completed", tenant_slug=None, error_message=None),
        SimpleNamespace(status="failed", tenant_slug="fc-test", error_message="S3 403"),
    ]
    platform_monitor.backups_failed("scheduled_daily", records)
    (event,) = _events(db, kind="backup.failed")
    assert event.details["failed"] == ["fc-test"]
    ((subject, body),) = _alert_mails(deliver)
    assert subject == "[Hubra] 1 of 2 scheduled backups failed"
    assert "S3 403" in body


def test_no_backup_alert_when_all_completed(db, staff, deliver):
    platform_monitor.backups_failed(
        "scheduled_daily",
        [SimpleNamespace(status="completed", tenant_slug=None, error_message=None)],
    )
    assert _events(db, category="backup") == []


def test_plugin_news_is_logged_but_mailed_only_on_request(db, staff, deliver):
    assert platform_monitor.default_prefs()["plugin_updates"] is False
    platform_monitor.plugin_news({"announced": ["budgets"], "failed": []})
    (event,) = _events(db, kind="plugin.updates")
    assert event.level == "info"
    assert _alert_mails(deliver) == []

    staff.platform_alerts = {"plugin_updates": True}
    db.session.commit()
    platform_monitor.plugin_news({"failed": ["discord"]})
    assert len(_alert_mails(deliver)) == 1
    assert _events(db, kind="plugin.updates")[-1].level == "warning"


def test_nothing_new_from_plugins_logs_nothing(db):
    platform_monitor.plugin_news({"mode": "off", "skipped": True})
    assert _events(db) == []


# ── Open problems ─────────────────────────────────────────────────────────────


def _fresh_health(**extra):
    return {"checked_at": time.time(), "services": {}, **extra}


def test_stale_background_jobs_are_a_problem(db):
    with patch("hubra.core.services.health_cache.HealthCache.get", return_value=None):
        ids = [p["id"] for p in platform_monitor.open_problems()]
    assert ids == ["jobs"]


def test_problems_from_services_relays_mail_and_backups(db, staff):
    from hubra.core.models.backup import BackupRecord

    platform_settings.set_many({"backup.s3.bucket": "hubra-backups"})
    db.session.add(
        BackupRecord(
            type="scheduled_daily",
            status="failed",
            scope="tenant",
            tenant_slug="fc-test",
            error_message="S3 403",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    platform_monitor.record("mail", "mail.failed", "x", level="error")
    platform_monitor._local_checks["relay"] = {"down": True, "error": "refused"}
    health = _fresh_health(
        watch={"db": {"fails": 3, "down_since": time.time() - 120}},
        services={"db": {"ok": False, "error": "timeout"}},
    )
    try:
        with patch("hubra.core.services.health_cache.HealthCache.get", return_value=health):
            problems = platform_monitor.open_problems()
    finally:
        platform_monitor._local_checks.clear()

    ids = [p["id"] for p in problems]
    assert set(ids) == {
        "service:db",
        "relay:relay",
        "mail:failed",
        "backup:failed",
        "backup:none",
    }
    # Errors before warnings.
    levels = [p["level"] for p in problems]
    assert levels == sorted(levels, key=lambda lvl: lvl != "error")


def test_all_quiet_means_no_problems(db):
    with patch("hubra.core.services.health_cache.HealthCache.get", return_value=_fresh_health()):
        assert platform_monitor.open_problems() == []


def test_overview_endpoint(client, staff_headers, db):
    platform_monitor.record(
        "alert", "backup_failed", "1 of 2 backups failed", level="error"
    )
    platform_monitor.record("backup", "backup.failed", "x", level="error")
    platform_monitor.record("mail", "mail.fallback", "y", level="warning")
    db.session.commit()
    with patch("hubra.core.services.health_cache.HealthCache.get", return_value=_fresh_health()):
        data = client.get(f"{BASE}/alerts/overview").get_json()
    assert data["problems"] == []
    assert [r["message"] for r in data["recent"]] == ["1 of 2 backups failed"]
    assert data["counts"] == {
        "backup": {"warning": 0, "error": 1},
        "mail": {"warning": 1, "error": 0},
    }


def test_overview_is_staff_only(client, auth_headers):
    assert client.get(f"{BASE}/alerts/overview").status_code == 403


# ── Alert mail layout ─────────────────────────────────────────────────────────


def test_alert_mail_uses_the_hubra_layout(db, staff, deliver):
    import json
    from email import message_from_string
    from pathlib import Path

    from hubra.core.models.translation import Translation

    seeds = Path(__file__).resolve().parents[2] / "hubra/core/seed_data/translations"
    texts = json.loads((seeds / "de-CH.json").read_text(encoding="utf-8"))
    for key, value in texts.items():
        if key.startswith("mail.email.platform_alert.") or key in {
            "mail.email.greeting",
            "mail.email.footer",
            "mail.email.sent_with",
        }:
            db.session.add(Translation(locale="de-CH", key=key, value=value))
    db.session.commit()

    platform_monitor.backups_failed(
        "scheduled_daily",
        [
            SimpleNamespace(
                status="failed", tenant_slug="fc-test", error_message="S3 403"
            )
        ],
    )
    (call,) = [c for c in deliver.call_args_list if "[Hubra]" in c.args[3]]
    msg = message_from_string(call.args[3])
    html = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    body = html.get_payload(decode=True).decode()
    assert "<html" in body.lower()
    assert "1 of 1 scheduled backups failed" in body
    assert "S3 403" in body
    assert "[mail." not in body  # every text is translated
    assert texts["mail.email.platform_alert.type.backup_failed"] in body
