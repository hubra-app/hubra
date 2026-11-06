"""The request id: taken from X-Request-ID or made, echoed, and carried on."""

from __future__ import annotations

from flask import g

from hubra.core import request_id


def test_a_new_id_is_made_and_echoed(client):
    res = client.get("/api/v1/global/version/")
    rid = res.headers.get("X-Request-ID")
    assert rid and len(rid) == 16


def test_an_incoming_id_is_kept(client):
    res = client.get("/api/v1/global/version/", headers={"X-Request-ID": "edge-abc.1"})
    assert res.headers["X-Request-ID"] == "edge-abc.1"


def test_an_unusable_id_is_replaced(client):
    res = client.get(
        "/api/v1/global/version/", headers={"X-Request-ID": "bad id <script>"}
    )
    assert res.headers["X-Request-ID"] != "bad id <script>"
    assert " " not in res.headers["X-Request-ID"]


def test_accept():
    assert request_id.accept("a" * 64) == "a" * 64
    assert request_id.accept("a" * 65) != "a" * 65
    assert request_id.accept(None)


def test_queued_tasks_carry_the_id(app, monkeypatch):
    from celery import Task

    from hubra.core.tasks.smoke import add

    seen = {}

    def fake(self, args=None, kwargs=None, **options):
        seen.update(options.get("headers") or {})

    monkeypatch.setattr(Task, "apply_async", fake)
    with app.test_request_context("/"):
        g.request_id = "req-1"
        add.apply_async((1, 2))
    assert seen["request_id"] == "req-1"


def test_outbox_envelopes_carry_the_id(app):
    from hubra.core.contracts.transport import envelope

    with app.test_request_context("/"):
        g.request_id = "req-2"
        env = envelope(
            kind="event", name="x.y", version=1, data={}, tenant_id=None, source="t"
        )
    assert env["hubrarequestid"] == "req-2"
