"""Post-deploy steps (services/post_deploy.py): run once per build after a
roll-out, stop at the first failure, report in the platform event log."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import (
    platform_monitor,
    platform_settings,
    post_deploy,
    upgrades,
)
from hubra.core.tasks import post_deploy_tasks, upgrade_tasks


@pytest.fixture
def alerts():
    sent: list[str] = []

    def fake(alert_type, subject, lines, *, level="error", throttle=True):
        sent.append(subject)
        return True

    with patch.object(platform_monitor, "alert", fake):
        yield sent


@pytest.fixture
def calls():
    """Replace the real steps with recorders; set ``fail`` to a key to fail it."""
    seen: list[str] = []
    state = {"fail": None}

    def make(key):
        def step():
            seen.append(key)
            if state["fail"] == key:
                raise RuntimeError(f"{key} broke")
            return f"{key} ok"

        return step

    fake = [(key, label, make(key)) for key, label, _args in post_deploy.STEPS]
    with patch.object(post_deploy, "_steps", lambda: fake):
        yield seen, state


def _runs(db):
    return list(
        db.session.execute(
            select(PlatformEvent)
            .where(PlatformEvent.kind == post_deploy.KIND)
            .order_by(PlatformEvent.id)
        ).scalars()
    )


def test_runs_every_step_in_order_and_records_it(db, calls, alerts):
    seen, _ = calls
    result = post_deploy.run("abc123")
    assert result["state"] == "done"
    assert seen == [key for key, _l, _a in post_deploy.STEPS]
    (event,) = _runs(db)
    assert event.level == "info"
    assert event.details["build"] == "abc123"
    assert [s["state"] for s in event.details["steps"]] == ["done"] * len(
        post_deploy.STEPS
    )
    assert post_deploy.ran_for("abc123")
    assert not post_deploy.ran_for("other")
    assert alerts == []


def test_a_failed_step_skips_the_rest_and_alerts(db, calls, alerts):
    seen, state = calls
    state["fail"] = "permissions"
    result = post_deploy.run("abc123")
    assert result["state"] == "failed"
    assert seen == ["migrate", "tenant_schemas", "permissions"]
    states = {s["key"]: s["state"] for s in result["steps"]}
    assert states["permissions"] == "failed"
    assert states["seed"] == "skipped" and states["plugins"] == "skipped"
    assert (
        "permissions broke"
        in next(s for s in result["steps"] if s["key"] == "permissions")["output"]
    )
    (event,) = _runs(db)
    assert event.level == "error"
    assert len(alerts) == 1


def test_setting_off_stops_automatic_runs_but_not_manual_ones(db, calls, alerts):
    seen, _ = calls
    platform_settings.set_many({post_deploy.SETTING: "off"})
    assert post_deploy.run("abc123")["state"] == "off"
    assert seen == []
    assert post_deploy.run(None, trigger="manual")["state"] == "done"
    assert _runs(db)[0].details["trigger"] == "manual"


def test_task_runs_once_per_build(db, calls, alerts):
    seen, _ = calls
    own = upgrades.build_key({"commit": None, "version": post_deploy_tasks_version()})
    task = post_deploy_tasks.run_post_deploy_steps
    assert task.run(own)["state"] == "done"
    assert task.run(own) == {"state": "already"}
    assert len(_runs(db)) == 1


def test_task_on_an_old_build_waits_for_a_new_worker(db, calls, alerts):
    seen, _ = calls
    with patch.object(
        post_deploy_tasks.run_post_deploy_steps,
        "retry",
        side_effect=RuntimeError("retry"),
    ):
        with pytest.raises(RuntimeError, match="retry"):
            post_deploy_tasks.run_post_deploy_steps.run("not-this-build")
    assert seen == []


def test_finished_upgrade_queues_the_steps(db):
    with (
        patch.object(
            upgrades, "check", lambda: {"state": "done", "build": {"commit": "fff999"}}
        ),
        patch.object(post_deploy_tasks.run_post_deploy_steps, "delay") as delay,
    ):
        upgrade_tasks.check_upgrades()
    delay.assert_called_once_with("fff999")
    with (
        patch.object(
            upgrades,
            "check",
            lambda: {"state": "rolling", "build": {"commit": "fff999"}},
        ),
        patch.object(post_deploy_tasks.run_post_deploy_steps, "delay") as delay,
    ):
        upgrade_tasks.check_upgrades()
    delay.assert_not_called()


def test_manage_starts_a_run_by_hand(client, staff_headers, db):
    with patch.object(post_deploy_tasks.run_post_deploy_steps, "delay") as delay:
        resp = client.post(
            "/api/v1/platform/upgrades/post-deploy", headers=staff_headers
        )
    assert resp.status_code == 202, resp.get_json()
    assert delay.call_args.args[1] == "manual"


def test_club_admin_cannot_start_a_run(client, auth_headers):
    assert (
        client.post(
            "/api/v1/platform/upgrades/post-deploy", headers=auth_headers
        ).status_code
        == 403
    )


def test_real_cli_steps_run_in_process(app, db):
    """The CLI steps (not the migration) run through the app's own commands."""
    for key, _label, step in post_deploy._steps():
        if key in ("tenant_schemas", "permissions"):
            out = step()
            assert out


def post_deploy_tasks_version():
    from hubra.core import build_info

    return build_info.version()
