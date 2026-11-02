"""Upgrade tracking (services/upgrades.py): baseline, started, done, stuck."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import platform_monitor, upgrades


def _proc(component, commit, host="pod-1", version="0.2.0"):
    return {"component": component, "host": host, "commit": commit, "version": version}


@pytest.fixture
def reports():
    """What the processes report; tests change the list in place."""
    current: list[dict] = []
    with patch("hubra.core.build_info.reported", lambda: list(current)):
        yield current


@pytest.fixture
def alerts():
    sent: list[tuple[str, str, str]] = []

    def fake(alert_type, subject, lines, *, level="error", throttle=True):
        sent.append((alert_type, subject, level))
        return True

    with patch.object(platform_monitor, "alert", fake):
        yield sent


def _kinds(db):
    return [
        e.kind
        for e in db.session.execute(
            select(PlatformEvent)
            .where(PlatformEvent.kind.like("upgrade.%"))
            .order_by(PlatformEvent.id)
        ).scalars()
    ]


def test_first_check_records_a_baseline_without_alert(db, reports, alerts):
    reports[:] = [_proc("api", "aaa111"), _proc("worker", "aaa111")]
    assert upgrades.check()["state"] == "baseline"
    assert _kinds(db) == ["upgrade.baseline"]
    assert alerts == []
    assert upgrades.check()["state"] == "steady"
    assert alerts == []


def test_rolling_upgrade_alerts_started_then_done(db, reports, alerts):
    reports[:] = [_proc("api", "aaa111"), _proc("worker", "aaa111")]
    upgrades.check()

    reports[:] = [_proc("api", "bbb222", version="0.3.0"), _proc("worker", "aaa111")]
    assert upgrades.check()["state"] == "started"
    assert alerts[-1][0] == "upgrades"
    assert "0.2.0 (aaa111) → 0.3.0 (bbb222)" in alerts[-1][1]

    assert upgrades.check()["state"] == "rolling"
    assert len(alerts) == 1

    reports[:] = [_proc("api", "bbb222", version="0.3.0"), _proc("worker", "bbb222", version="0.3.0")]
    assert upgrades.check()["state"] == "done"
    assert alerts[-1][1].startswith("Upgrade completed")
    assert _kinds(db) == ["upgrade.baseline", "upgrade.started", "upgrade.done"]
    assert upgrades.check()["state"] == "steady"
    assert upgrades.last_upgrade()["kind"] == "upgrade.done"


def test_upgrade_done_between_checks_sends_one_alert(db, reports, alerts):
    reports[:] = [_proc("api", "aaa111"), _proc("worker", "aaa111")]
    upgrades.check()
    reports[:] = [_proc("api", "ccc333"), _proc("worker", "ccc333")]
    assert upgrades.check()["state"] == "done"
    assert [a[1].split(":")[0] for a in alerts] == ["Upgrade completed"]


def test_stuck_upgrade_warns_once(db, reports, alerts):
    reports[:] = [_proc("api", "aaa111"), _proc("worker", "aaa111")]
    upgrades.check()
    reports[:] = [_proc("api", "bbb222"), _proc("worker", "aaa111")]
    upgrades.check()
    started = upgrades.last_event()
    started.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    db.session.commit()

    assert upgrades.check()["state"] == "stuck"
    assert alerts[-1][2] == "warning"
    assert upgrades.check()["state"] == "rolling"
    assert sum(1 for a in alerts if a[2] == "warning") == 1


def test_dev_builds_are_told_apart_by_version(db, reports, alerts):
    reports[:] = [_proc("api", None, version="0.2.0")]
    upgrades.check()
    reports[:] = [_proc("api", None, version="0.3.0")]
    assert upgrades.check()["state"] == "done"
    assert "0.2.0 → 0.3.0" in alerts[-1][1]


def test_upgrades_is_an_alert_type_on_by_default():
    assert platform_monitor.default_prefs()["upgrades"] is True
