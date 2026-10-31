"""Support impersonating a member sees the club as they do, but doesn't end
their membership or their sessions for them."""

from flask_jwt_extended import create_access_token


def _sign_in(app, client, member, **claims):
    with app.app_context():
        token = create_access_token(identity=str(member.id), additional_claims=claims)
    client.set_cookie("access_token_cookie", token)


IMPERSONATING = {
    "impersonator_id": 99,
    "impersonator_user_id": 99,
    "impersonation_reason": "support",
    "impersonation_expires_at": "2099-01-01T00:00:00+00:00",
    "impersonation_mode": "act",
}


def test_support_cannot_leave_the_club_or_end_sessions(app, client, seeded_db):
    member = seeded_db["admin"]
    _sign_in(app, client, member, **IMPERSONATING)
    for method, path in (
        ("post", "/api/v1/members/me/leave"),
        ("post", "/api/v1/account/sessions/revoke-all"),
        ("delete", "/api/v1/account/sessions/1"),
        ("delete", "/api/v1/account/devices/1"),
        ("post", "/api/v1/account/all-sessions/revoke-all"),
        ("delete", "/api/v1/account/all-sessions/test/1"),
    ):
        resp = getattr(client, method)(path, json={})
        assert resp.status_code == 403, path
        assert resp.get_json()["error"] == "IMPERSONATION_RESTRICTED"
    assert member.archived_at is None


def test_sign_out_elsewhere_without_a_tracked_session(app, client, seeded_db):
    _sign_in(app, client, seeded_db["admin"])
    resp = client.post("/api/v1/account/sessions/revoke-all", json={})
    assert resp.status_code == 200


def test_support_only_looks_unless_changes_were_allowed(app, client, seeded_db):
    looking = {k: v for k, v in IMPERSONATING.items() if k != "impersonation_mode"}
    _sign_in(app, client, seeded_db["admin"], **looking)
    assert client.get("/api/v1/members/").status_code == 200
    resp = client.post("/api/v1/groups/", json={"name": "Support was here"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "IMPERSONATION_READ_ONLY"
    body = client.get("/api/v1/account/permissions").get_json()
    assert body["impersonation"]["read_only"] is True
