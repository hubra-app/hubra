"""Each member chooses which contact data other members see in the club's
directory. Nothing until they choose; those who manage members see it all."""

from tests.settings.test_settings_kv import _login, _make_role_and_member

_READ = ["members.members.read"]


def _two_members(app, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    shy = _make_role_and_member(db, seeded_db["tier"], name="Shy", permission_keys=_READ)
    shy.user.phone = "+41 79 000 00 00"
    shy.user.address_city = "Bern"
    _make_role_and_member(db, seeded_db["tier"], name="Peer", permission_keys=_READ)
    db.session.commit()
    return shy


def test_contact_data_is_hidden_until_the_member_shares_it(client, app, db, seeded_db):
    shy = _two_members(app, db, seeded_db)

    _login(client, "peer@test.ch")
    row = client.get(f"/api/v1/members/{shy.id}").get_json()
    assert row["email"] is None and row["phone"] is None
    assert row["address_city"] is None
    assert row["first_name"] == "Test"

    _login(client, "shy@test.ch")
    # The member always sees their own data.
    assert client.get(f"/api/v1/members/{shy.id}").get_json()["phone"]
    resp = client.put("/api/v1/members/me/directory", json={"shared": ["phone"]})
    assert resp.status_code == 200 and resp.get_json()["shared"] == ["phone"]

    _login(client, "peer@test.ch")
    row = client.get(f"/api/v1/members/{shy.id}").get_json()
    assert row["phone"] == "+41 79 000 00 00"
    assert row["email"] is None and row["address_city"] is None
    listed = client.get("/api/v1/members/").get_json()["data"]
    assert {m["id"]: m["phone"] for m in listed}[shy.id] == "+41 79 000 00 00"


def test_hidden_data_cannot_be_found_by_search(client, app, db, seeded_db):
    _two_members(app, db, seeded_db)
    _login(client, "peer@test.ch")
    found = client.get("/api/v1/members/?search=shy@test").get_json()["data"]
    assert found == []
    assert client.get("/api/v1/members/?search=Shy").get_json()["data"]


def test_admins_see_everything(client, auth_headers, app, db, seeded_db):
    shy = _two_members(app, db, seeded_db)
    _login(client, "admin@test.ch")
    row = client.get(f"/api/v1/members/{shy.id}").get_json()
    assert row["email"] == "shy@test.ch" and row["address_city"] == "Bern"


def test_only_known_choices(client, app, db, seeded_db):
    _two_members(app, db, seeded_db)
    _login(client, "shy@test.ch")
    bad = client.put("/api/v1/members/me/directory", json={"shared": ["notes"]})
    assert bad.status_code == 422
