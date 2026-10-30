"""A function can give its holders a role (Kassier gives Treasurer).

The role is derived from holding the function, never copied onto the
member: leaving the function or the end of the term takes it away.
"""

from datetime import date, timedelta

from hubra.core.models.function import FunctionHolder

from tests.authz.conftest import _create_member_with_role, _login_member


def _admin(client):
    return _login_member(client, "admin@test.ch")


def _kasse(db, seeded_db):
    """A role that may read the functions list, and a member without it."""
    tier = seeded_db["tier"]
    _, kasse = _create_member_with_role(
        "kasse-holder@test.ch", "Kasse", tier.id, permission_keys=["functions.functions.read"]
    )
    plain, _ = _create_member_with_role("plain@test.ch", "Plain", tier.id)
    db.session.commit()
    return kasse, plain


def test_holder_gets_the_role_while_holding(client, db, seeded_db):
    kasse, plain = _kasse(db, seeded_db)

    _admin(client)
    resp = client.post(
        "/api/v1/functions/", json={"name": "Kassier", "grantsRoleId": kasse.id}
    )
    assert resp.status_code == 201
    fn_id = resp.get_json()["id"]
    assert resp.get_json()["grantsRoleId"] == kasse.id

    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/functions/").status_code == 403

    _admin(client)
    resp = client.post(f"/api/v1/functions/{fn_id}/holders", json={"memberId": plain.id})
    assert resp.status_code == 201

    # The members list says where the role comes from, and filters by it.
    resp = client.get(f"/api/v1/members/?role_id={kasse.id}&pageSize=100")
    rows = {m["id"]: m for m in resp.get_json()["data"]}
    assert plain.id in rows
    assert rows[plain.id]["function_roles"] == [
        {"id": kasse.id, "name": "Kasse", "function": "Kassier"}
    ]

    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/functions/").status_code == 200

    _admin(client)
    resp = client.delete(f"/api/v1/functions/{fn_id}/holders/{plain.id}")
    assert resp.status_code == 200

    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/functions/").status_code == 403


def test_an_ended_term_gives_no_role(client, db, seeded_db):
    kasse, plain = _kasse(db, seeded_db)
    _admin(client)
    fn_id = client.post(
        "/api/v1/functions/", json={"name": "Kassier", "grantsRoleId": kasse.id}
    ).get_json()["id"]
    db.session.add(
        FunctionHolder(
            function_id=fn_id,
            member_id=plain.id,
            term_end=date.today() - timedelta(days=1),
        )
    )
    db.session.commit()

    _login_member(client, "plain@test.ch")
    assert client.get("/api/v1/functions/").status_code == 403


def test_no_function_gives_the_owner_role(client, db, seeded_db):
    _admin(client)
    resp = client.post(
        "/api/v1/functions/",
        json={"name": "Präsidium", "grantsRoleId": seeded_db["owner_role"].id},
    )
    assert resp.status_code == 400


def test_linking_needs_the_right_to_give_the_role(client, db, seeded_db):
    """Holding functions.update is not enough to hand out a stronger role."""
    kasse, plain = _kasse(db, seeded_db)
    _admin(client)
    fn_id = client.post(
        "/api/v1/functions/", json={"name": "Kassier", "grantsRoleId": kasse.id}
    ).get_json()["id"]

    _create_member_with_role(
        "fn-editor@test.ch",
        "FnEditor",
        seeded_db["tier"].id,
        permission_keys=["functions.functions.update"],
    )
    db.session.commit()
    _login_member(client, "fn-editor@test.ch")

    resp = client.post(f"/api/v1/functions/{fn_id}/holders", json={"memberId": plain.id})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "BEYOND_OWN_PERMISSIONS"


def test_roles_list_counts_holders(client, db, seeded_db):
    kasse, plain = _kasse(db, seeded_db)
    _admin(client)
    fn_id = client.post(
        "/api/v1/functions/", json={"name": "Kassier", "grantsRoleId": kasse.id}
    ).get_json()["id"]
    client.post(f"/api/v1/functions/{fn_id}/holders", json={"memberId": plain.id})

    counts = {r["id"]: r["member_count"] for r in client.get("/api/v1/roles/").get_json()}
    # kasse-holder@ holds it directly, plain@ through the function.
    assert counts[kasse.id] == 2
    assert counts[seeded_db["owner_role"].id] == 1
