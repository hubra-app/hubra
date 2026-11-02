"""POST /auth/redirect-loop: a stopped redirect loop lands in the event log."""

from __future__ import annotations

from hubra.core.models.platform_event import PlatformEvent

URL = "/api/v1/auth/redirect-loop"

HOPS = [
    {
        "ms": 0,
        "from": "app.hubra.club/demo/app/dashboard",
        "to": "sso.hubra.club/login",
        "why": "no-club",
    },
    {
        "ms": 400,
        "from": "sso.hubra.club/login",
        "to": "app.hubra.club/demo/app/dashboard",
        "why": "signed-in",
    },
]


def _events(db):
    return db.session.query(PlatformEvent).filter_by(kind="redirect_loop").all()


def test_anonymous_report_is_logged(client, db):
    resp = client.post(
        URL, json={"page": "app.hubra.club/demo/app/dashboard", "hops": HOPS * 3}
    )
    assert resp.status_code == 202
    [event] = _events(db)
    assert event.category == "system"
    assert event.level == "warning"
    assert "6 redirects" in event.message
    assert "no-club" in event.message and "signed-in" in event.message
    assert event.details["session"] == {}
    assert len(event.details["hops"]) == 6


def test_signed_in_report_names_the_session(client, db, auth_headers):
    client.post(URL, json={"hops": HOPS})
    [event] = _events(db)
    assert event.details["session"].get("user_id")


def test_no_query_hash_or_odd_characters_are_kept(client, db):
    client.post(
        URL,
        json={
            "page": "sso.hubra.club/verify?token=secret#t=secret2",
            "hops": [
                {
                    "ms": "nonsense",
                    "from": "app.hubra.club/x?redirect=https://a/b?token=secret",
                    "to": "sso.hubra.club/login#token=secret <script>",
                    "why": "Anon<script>",
                }
            ],
        },
    )
    [event] = _events(db)
    text = f"{event.message} {event.details}"
    assert "secret" not in text
    assert "<" not in text
    hop = event.details["hops"][0]
    assert hop == {
        "ms": 0,
        "from": "app.hubra.club/x",
        "to": "sso.hubra.club/login",
        "why": "anonscript",
    }


def test_hops_are_capped_and_garbage_refused(client, db):
    assert client.post(URL, json={"hops": "nope"}).status_code == 400
    assert client.post(URL, json={}).status_code == 400
    client.post(URL, json={"hops": HOPS * 20})
    [event] = _events(db)
    assert len(event.details["hops"]) == 12
