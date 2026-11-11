"""Background job dashboard: manage › Diagnose › Hintergrundjobs."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hubra.core.services import job_monitor

BASE = "/api/v1/manager/platform/jobs"


@pytest.fixture(autouse=True)
def _clean():
    job_monitor.reset_local()
    with (
        patch.object(job_monitor, "_redis", return_value=None),
        patch.object(job_monitor, "_reader", return_value=None),
    ):
        yield
    job_monitor.reset_local()


def _fail(task="hubra.core.tasks.email_tasks.send_email_task", **kw):
    job_monitor.count(task, "failed")
    job_monitor.failed(
        task_id="t-1",
        task=task,
        args=kw.pop("args", ["to@example.ch"]),
        kwargs=kw.pop("kwargs", {"subject": "Hallo", "html": "<b>secret link</b>"}),
        exception=RuntimeError("SMTP down"),
        tenant_id=kw.pop("tenant_id", None),
    )


def test_counts_running_and_failures(client, staff_headers):
    job_monitor.count("a.task", "sent")
    job_monitor.count("a.task", "sent")
    job_monitor.count("a.task", "done", 120)
    job_monitor.count("a.task", "retried")
    job_monitor.started("run-1", "b.task", 7)
    _fail()

    body = client.get(BASE).get_json()
    assert body["totals"] == {"sent": 2, "done": 1, "failed": 1, "retried": 1}
    a = next(t for t in body["tasks"] if t["task"] == "a.task")
    assert a["avg_ms"] == 120
    assert body["queued"] is None  # no broker in tests
    assert [r["task"] for r in body["running"]] == ["b.task"]

    (f,) = body["failed"]
    assert f["error"] == "RuntimeError: SMTP down"
    assert f["can_retry"] is True
    assert f["args"] == ["to@example.ch"]
    # Values of keys that look secret are hidden.
    assert f["kwargs"] == {"subject": "Hallo", "html": "•••"}
    assert "payload" not in f

    assert job_monitor.finished("run-1") is not None
    assert client.get(BASE).get_json()["running"] == []


def test_retry_sends_the_job_again(client, staff_headers, db, tenant_pair):
    _fail(tenant_id=tenant_pair["tenant_a"].id)
    (f,) = client.get(BASE).get_json()["failed"]
    assert f["club"] == "Tenant A"

    from hubra.core.tasks import celery_app

    # Not patch.dict on celery_app.tasks: retry() imports every task module,
    # and restoring the registry afterwards would drop them for later tests.
    with patch.object(celery_app, "send_task") as send:
        send.return_value.id = "new-id"
        resp = client.post(f"{BASE}/failed/{f['id']}/retry")
    assert resp.status_code == 200, resp.get_json()
    send.assert_called_once_with(
        f["task"],
        args=["to@example.ch"],
        kwargs={"subject": "Hallo", "html": "<b>secret link</b>"},
        headers={"tenant_id": tenant_pair["tenant_a"].id},
    )
    job = resp.get_json()["job"]
    assert job["retry_task_id"] == "new-id"
    assert job["retried_by"] == "admin@test.ch"

    from hubra.core.models.tenant import GlobalAuditEntry

    assert (
        db.session.query(GlobalAuditEntry)
        .filter_by(action="platform.job.retry")
        .count()
        == 1
    )


def test_retry_refuses_unknown_tasks_and_large_jobs(client, staff_headers):
    _fail(task="not.a.real.task")
    (f,) = client.get(BASE).get_json()["failed"]
    assert client.post(f"{BASE}/failed/{f['id']}/retry").status_code == 409

    job_monitor.reset_local()
    _fail(args=["x" * 20_000])
    (f,) = client.get(BASE).get_json()["failed"]
    assert f["can_retry"] is False
    assert client.post(f"{BASE}/failed/{f['id']}/retry").status_code == 409
    assert client.post(f"{BASE}/failed/nope/retry").status_code == 404


def test_dismiss(client, staff_headers):
    _fail()
    (f,) = client.get(BASE).get_json()["failed"]
    assert client.delete(f"{BASE}/failed/{f['id']}").status_code == 200
    assert client.get(BASE).get_json()["failed"] == []
    assert client.delete(f"{BASE}/failed/{f['id']}").status_code == 404


def test_failed_task_is_recorded_by_the_signal(app):
    from hubra.core.tasks import celery_app

    @celery_app.task(name="tests.job_monitor.boom")
    def boom(x, flag=False):
        raise ValueError("bad input")

    try:
        boom.apply(args=(5,), kwargs={"flag": True}, throw=False)
    finally:
        celery_app.tasks.pop("tests.job_monitor.boom", None)
    (entry,) = job_monitor.failures()
    assert entry["task"] == "tests.job_monitor.boom"
    assert entry["payload"] == {"args": [5], "kwargs": {"flag": True}}
    assert "ValueError: bad input" in entry["error"]
    assert job_monitor.running() == []


def test_needs_platform_rights(client, auth_headers):
    assert client.get(BASE).status_code in (401, 403)


def test_secret_positional_args_are_hidden(client, staff_headers):
    # approve_request(req_id, user_id, interaction_token): the token comes
    # by position, and is hidden like a keyword one.
    _fail(
        task="hubra.core.tasks.platform_bot_tasks.approve_request",
        args=[5, 7, "discord-interaction-token"],
        kwargs={},
    )
    (f,) = client.get(BASE).get_json()["failed"]
    assert f["args"] == [5, 7, "•••"]
