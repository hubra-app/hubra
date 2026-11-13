"""The club search: every module's ``<module>.search`` in one answer
(roadmap idea 39)."""

from __future__ import annotations

from datetime import date

import pytest

from hubra.core.contracts.search import search_contract
from hubra.core.extensions import db
from hubra.core.modules import Module, registry
from tests.events.test_m5_events import _create_event
from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

URL = "/api/v1/app/search/"


def tools(ctx, data):
    return {
        "hits": [
            {
                "id": "item:1",
                "label": f"Bohrmaschine ({data.q})",
                "path": "/app/inventory/1",
                "kind": "item",
            }
        ]
    }


@pytest.fixture
def tools_module(app, seeded_db):
    registry.load()
    registry._modules["tools"] = Module(
        code="tools",
        name="Tools",
        provides=(search_contract("tools", f"{__name__}:tools"),),
    )
    set_modules(True, "tools")
    yield
    registry._modules.pop("tools", None)


def _hits(client, q, **kw):
    resp = client.get(URL, query_string={"q": q}, **kw)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["hits"]


def test_finds_members_events_and_plugin_items(
    client, auth_headers, seeded_db, tools_module
):
    from hubra.core.models.finance import Invoice

    _create_event(client, auth_headers, title="Sommerfest am See", date="2030-06-06")
    admin_id = seeded_db["admin"].id
    db.session.add(
        Invoice(
            member_id=admin_id,
            issued=date(2026, 1, 1),
            due=date(2026, 2, 1),
            amount=45,
            status="Open",
            description="Sommerfest Beitrag",
        )
    )
    db.session.commit()

    hits = _hits(client, "sommerfest", headers=auth_headers)
    by_source = {h["source"]: h for h in hits}
    assert by_source["events"]["label"] == "Sommerfest am See"
    assert "event=" in by_source["events"]["path"]
    assert by_source["finance"]["kind"] == "invoice"
    assert by_source["tools"]["label"] == "Bohrmaschine (sommerfest)"

    admin = seeded_db["admin"].user
    hits = _hits(
        client, f"{admin.first_name[:3]} {admin.last_name[:3]}", headers=auth_headers
    )
    assert any(h["path"] == f"/app/members/{admin_id}" for h in hits)


def test_rights_decide_what_is_searched(client, app, auth_headers, seeded_db):
    _create_event(client, auth_headers, title="Sommerfest", date="2030-06-06")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["posts.posts.read"]
    )
    client.post("/api/v1/auth/logout")
    _login(client, "reader@test.ch")
    hits = _hits(client, "sommerfest")
    assert all(h["source"] not in ("events", "finance", "members") for h in hits)
    # Contact data is only searched by those who see it all.
    assert _hits(client, "admin@test.ch") == []


def test_signed_out_and_bad_queries(client, auth_headers, seeded_db):
    assert (
        client.get(URL, query_string={"q": "a"}, headers=auth_headers).status_code
        == 400
    )
    assert client.get(URL, headers=auth_headers).status_code == 400
    client.post("/api/v1/auth/logout")
    assert client.get(URL, query_string={"q": "abc"}).status_code == 401
