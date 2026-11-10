"""Own dashboards: private until shared, shared ones for every member."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.models.dashboard import Dashboard
from tests.authz.conftest import (  # noqa: F401
    _login_member,
    permissioned_member_factory,
    plain_member_token,
)

ADMIN = "admin@test.ch"
PLAIN = "plain@test.ch"
SHARER = "sharer@test.ch"


def _as(client, email):
    """Sign in as *email* (the test client keeps one session cookie)."""
    return _login_member(client, email)


URL = "/api/v1/app/dashboards/"
WIDGETS = [
    {"id": "a", "type": "events.upcoming", "size": "m", "config": {"count": 5}},
    {"id": "b", "type": "note", "size": "s", "config": {"text": "Hallo"}},
]


def _create(client, headers, **body):
    return client.post(URL, json={"name": "Vorstand", **body}, headers=headers)


def test_member_creates_and_edits_a_private_dashboard(client, plain_member_token):  # noqa: F811
    resp = _create(client, plain_member_token, widgets=WIDGETS)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["shared"] is False and body["mine"] and body["canEdit"]
    assert [w["id"] for w in body["widgets"]] == ["a", "b"]

    did = body["id"]
    resp = client.patch(
        f"{URL}{did}",
        json={"name": "Meine Sicht", "widgets": WIDGETS[:1]},
        headers=plain_member_token,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Meine Sicht"
    assert len(resp.get_json()["widgets"]) == 1
    listed = client.get(URL, headers=plain_member_token).get_json()
    assert [d["name"] for d in listed["items"]] == ["Meine Sicht"]
    assert listed["canShare"] is False


def test_widgets_are_checked(client, plain_member_token):  # noqa: F811
    bad = [
        [{"id": "a", "type": "Bad Type!"}],
        [{"id": "a", "type": "note"}, {"id": "a", "type": "note"}],
        [{"id": "a", "type": "note", "size": "xl"}],
        [{"id": "a", "type": "note", "config": "x"}],
        [{"id": "a", "type": "note", "config": {"text": "x" * 5000}}],
        [{"id": f"w{i}", "type": "note"} for i in range(25)],
        [{"id": "a", "type": "note", "w": 1}],
        [{"id": "a", "type": "note", "w": 13}],
        [{"id": "a", "type": "note", "h": 0}],
        [{"id": "a", "type": "note", "h": 25}],
        [{"id": "a", "type": "note", "h": 2.5}],
        [{"id": "a", "type": "note", "w": True}],
        "nope",
    ]
    for widgets in bad:
        resp = _create(client, plain_member_token, widgets=widgets)
        assert resp.status_code == 400, widgets
    assert _create(client, plain_member_token, name="  ").status_code == 400


def test_widgets_keep_their_place_on_the_grid(client, plain_member_token):  # noqa: F811
    widgets = [
        {"id": "a", "type": "note", "w": 7, "h": 5},
        {"id": "b", "type": "note", "size": "s", "w": 3},
        {"id": "c", "type": "note", "w": 12},
        {"id": "d", "type": "note", "size": "l"},
    ]
    resp = _create(client, plain_member_token, widgets=widgets)
    assert resp.status_code == 201, resp.get_json()
    saved = resp.get_json()["widgets"]
    assert [(w["size"], w.get("w"), w.get("h")) for w in saved] == [
        ("m", 7, 5),  # size follows the width when the app doesn't send one
        ("s", 3, None),
        ("l", 12, None),
        ("l", None, None),  # an old widget without a grid size stays as it was
    ]


def test_built_in_camel_case_types_save(client, plain_member_token):  # noqa: F811
    # The club start page's built-in layout starts with polls.voteNeeded; a
    # lowercase-only check made every change to it fail with 400.
    widgets = [
        {"id": "vote", "type": "polls.voteNeeded", "size": "l"},
        {"id": "inv", "type": "stat.openInvoices", "size": "s"},
        {"id": "plug", "type": "p:inventory.checkedOut", "size": "m"},
    ]
    resp = _create(client, plain_member_token, widgets=widgets)
    assert resp.status_code == 201, resp.get_json()
    assert [w["type"] for w in resp.get_json()["widgets"]] == [w["type"] for w in widgets]


def test_private_dashboards_stay_private(client, auth_headers, plain_member_token):  # noqa: F811
    did = _create(client, plain_member_token).get_json()["id"]
    _as(client, ADMIN)
    other = client.get(f"{URL}{did}", headers=auth_headers)
    # Admins may tidy up, but see only shared ones in their list.
    assert other.status_code == 200
    names = [
        d["name"] for d in client.get(URL, headers=auth_headers).get_json()["items"]
    ]
    assert names == []


def test_sharing_needs_the_right(
    client,
    auth_headers,
    plain_member_token,  # noqa: F811
    permissioned_member_factory,  # noqa: F811
):
    permissioned_member_factory(["dashboards.dashboards.share"], email=SHARER)
    did = _create(client, {}, widgets=WIDGETS).get_json()["id"]
    _as(client, PLAIN)
    mine = _create(client, {}).get_json()["id"]

    # Without the right: 403.
    resp = client.put(f"{URL}{mine}/sharing", json={"shared": True})
    assert resp.status_code == 403

    _as(client, SHARER)
    resp = client.put(f"{URL}{did}/sharing", json={"shared": True})
    assert resp.status_code == 200 and resp.get_json()["shared"] is True
    # Someone else's private dashboard is not found.
    assert client.get(f"{URL}{mine}").status_code == 404

    # Every member now sees it, but can't change it.
    _as(client, PLAIN)
    listed = client.get(URL).get_json()["items"]
    shared = next(d for d in listed if d["id"] == did)
    assert shared["mine"] is False and shared["canEdit"] is False
    assert client.patch(f"{URL}{did}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{URL}{did}").status_code == 403

    # An admin may stop sharing it, not share someone else's.
    _as(client, ADMIN)
    resp = client.put(f"{URL}{did}/sharing", json={"shared": False})
    assert resp.status_code == 200 and resp.get_json()["shared"] is False
    resp = client.put(f"{URL}{mine}/sharing", json={"shared": True})
    assert resp.status_code == 403


def test_owner_deletes(client, plain_member_token):  # noqa: F811
    did = _create(client, plain_member_token).get_json()["id"]
    assert client.delete(f"{URL}{did}", headers=plain_member_token).status_code == 204
    assert db.session.get(Dashboard, did) is None


def test_limit_per_member(client, plain_member_token, monkeypatch):  # noqa: F811
    from hubra.api.dashboards import routes

    monkeypatch.setattr(routes, "MAX_DASHBOARDS", 2)
    assert _create(client, plain_member_token).status_code == 201
    assert _create(client, plain_member_token).status_code == 201
    assert _create(client, plain_member_token).status_code == 409


HOME = f"{URL}home"


def test_start_pages_default_to_built_in(client, plain_member_token):  # noqa: F811
    body = client.get(HOME, headers=plain_member_token).get_json()
    assert body["club"]["widgets"] is None and body["club"]["canEdit"] is False
    assert body["me"]["widgets"] is None and body["me"]["canEdit"] is True


def test_member_changes_own_start_page(client, plain_member_token):  # noqa: F811
    resp = client.put(f"{HOME}/me", json={"widgets": WIDGETS}, headers=plain_member_token)
    assert resp.status_code == 200
    assert [w["id"] for w in resp.get_json()["widgets"]] == ["a", "b"]
    assert client.put(f"{HOME}/me", json={"widgets": "x"}).status_code == 400
    # A start page is not a dashboard tab and doesn't count to the limit.
    listed = client.get(URL).get_json()["items"]
    assert listed == []
    # Others keep the built-in one.
    _as(client, ADMIN)
    assert client.get(HOME).get_json()["me"]["widgets"] is None
    _as(client, PLAIN)
    assert client.delete(f"{HOME}/me").status_code == 200
    assert client.get(HOME).get_json()["me"]["widgets"] is None


def test_club_start_page_needs_the_right(
    client,
    auth_headers,
    plain_member_token,  # noqa: F811
):
    assert client.put(f"{HOME}/club", json={"widgets": WIDGETS}).status_code == 403
    assert client.delete(f"{HOME}/club").status_code == 403

    _as(client, ADMIN)
    assert client.get(HOME).get_json()["club"]["canEdit"] is True
    resp = client.put(f"{HOME}/club", json={"widgets": WIDGETS[:1]})
    assert resp.status_code == 200
    row = db.session.scalars(
        db.select(Dashboard).where(Dashboard.home == "club")
    ).one()
    # Its id can't be reached as a dashboard.
    assert client.get(f"{URL}{row.id}").status_code == 404

    # Every member sees the club's start page.
    _as(client, PLAIN)
    club = client.get(HOME).get_json()["club"]
    assert [w["id"] for w in club["widgets"]] == ["a"]

    _as(client, ADMIN)
    assert client.delete(f"{HOME}/club").status_code == 200
    assert client.get(HOME).get_json()["club"]["widgets"] is None
