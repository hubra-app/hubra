"""Which clubs use which modules and plugins (services.module_usage,
manage › Plugins › Nutzung)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hubra.core.models.post import Post
from hubra.core.models.tenant import Tenant
from hubra.core.services import module_usage, platform_bot
from hubra.core.tenant.context import current_tenant

URL = "/api/v1/manager/plugins/usage"


@pytest.fixture
def clubs(db):
    a = Tenant(name="Alpha", slug="alpha", plan="starter", status="active")
    b = Tenant(name="Beta", slug="beta", plan="starter", status="active")
    gone = Tenant(name="Gone", slug="gone", plan="starter", status="suspended")
    db.session.add_all([a, b, gone])
    db.session.commit()
    return a, b


@pytest.fixture
def local_store(monkeypatch):
    monkeypatch.setattr(platform_bot, "_redis", lambda: None)
    platform_bot._local.pop(module_usage.KEY, None)
    yield
    platform_bot._local.pop(module_usage.KEY, None)


def _row(data, code):
    return next(m for m in data["modules"] if m["code"] == code)


def test_on_used_and_idle_per_module(clubs, monkeypatch):
    a, b = clubs
    on = {a.id: ["core", "posts", "events"], b.id: ["core", "posts"]}
    monkeypatch.setattr(
        "hubra.core.modules.state.enabled_codes", lambda tid=None: on.get(tid, [])
    )
    # Alpha wrote posts, Beta didn't.
    monkeypatch.setattr(
        module_usage,
        "_touched",
        lambda tables, since: 4 if current_tenant().slug == "alpha" else 0,
    )
    with patch("hubra.core.tenant.context.set_search_path"):
        data = module_usage.compute()

    assert data["clubs"] == 2  # the suspended club doesn't count
    posts = _row(data, "posts")
    assert (posts["clubsOn"], posts["clubsActive"], posts["clubsIdle"]) == (2, 1, 1)
    assert posts["rows"] == 4
    assert posts["idle"] == [{"id": b.id, "name": "Beta"}]
    events = _row(data, "events")
    assert (events["clubsOn"], events["clubsActive"]) == (1, 1)
    assert _row(data, "polls")["clubsOn"] == 0


def test_rows_count_by_their_timestamp(db, seeded_db):
    member = seeded_db["admin"]
    now = datetime.now(timezone.utc)
    db.session.add_all(
        [
            Post(author_id=member.id, title="New", body="x", created_at=now),
            Post(
                author_id=member.id,
                title="Old",
                body="x",
                created_at=now - timedelta(days=60),
                updated_at=now - timedelta(days=60),
            ),
        ]
    )
    db.session.commit()
    since = now - timedelta(days=30)
    assert module_usage._touched(("posts",), since) == 1
    # Unknown tables and tables without a timestamp count nothing.
    assert module_usage._touched(("no_such_table",), since) == 0


def test_plugins_count_clubs_with_any_of_their_modules(clubs, monkeypatch):
    a, b = clubs
    monkeypatch.setattr(
        "hubra.core.modules.state.enabled_codes",
        lambda tid=None: ["posts"] if tid == a.id else [],
    )
    monkeypatch.setattr(module_usage, "_touched", lambda tables, since: 0)
    monkeypatch.setattr(
        module_usage,
        "_plugins",
        lambda: {
            "unused": {
                "id": "unused",
                "name": "Unused",
                "version": "1.0.0",
                "modules": [],
            }
        },
    )
    with patch("hubra.core.tenant.context.set_search_path"):
        data = module_usage.compute()
    assert data["plugins"] == [
        {
            "id": "unused",
            "name": "Unused",
            "version": "1.0.0",
            "modules": [],
            "clubsOn": 0,
        }
    ]


def test_the_last_count_is_kept(clubs, local_store, monkeypatch):
    monkeypatch.setattr(module_usage, "compute", lambda days=30: {"clubs": 2})
    assert module_usage.latest() is None
    module_usage.refresh()
    assert module_usage.latest() == {"clubs": 2}


def test_platform_staff_read_and_count(client, staff_headers, local_store, monkeypatch):
    assert client.get(URL).get_json() == {"usage": None}
    monkeypatch.setattr(module_usage, "compute", lambda days=30: {"clubs": 0})
    resp = client.post(f"{URL}/refresh")
    assert resp.status_code == 200, resp.get_json()
    assert client.get(URL).get_json() == {"usage": {"clubs": 0}}


def test_club_admins_and_strangers_cannot(client, auth_headers, app):
    assert client.get(URL).status_code == 403
    assert client.post(f"{URL}/refresh").status_code == 403
    anon = app.test_client()
    assert anon.get(URL).status_code == 401


def test_the_nightly_task_is_scheduled():
    import hubra.core.tasks.plugin_tasks  # noqa: F401  (registers the task)
    from hubra.core.tasks import celery_app

    entry = celery_app.conf.beat_schedule["usage-snapshot-nightly"]
    assert entry["task"] == "hubra.core.tasks.plugin_tasks.usage_snapshot"
    assert entry["task"] in celery_app.tasks
