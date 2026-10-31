"""A group's leader and a function's holder see their own address and switch
it on or off, without the club-wide alias rights."""

from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.group import Group
from tests.mail.test_mail_features import _make_mma
from tests.settings.test_settings_kv import _login, _make_role_and_member


def _setup(app, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    lead = _make_role_and_member(db, seeded_db["tier"], name="Lena", permission_keys=[])
    mine, other = Group(name="Youth", lead_id=lead.id), Group(name="Seniors")
    fn = Function(name="Kassier")
    db.session.add_all([mine, other, fn])
    db.session.flush()
    db.session.add(FunctionHolder(function_id=fn.id, member_id=lead.id))
    for owner_type, owner_id, address in (
        ("group", mine.id, "youth@club.ch"),
        ("group", other.id, "seniors@club.ch"),
        ("function", fn.id, "kassier@club.ch"),
    ):
        _make_mma(
            db,
            address=address,
            address_type="mailbox",
            owner_type=owner_type,
            owner_id=owner_id,
            kind=owner_type,
        )
    db.session.commit()
    return mine.id, other.id, fn.id


def test_leader_and_holder_reach_their_own_address(client, app, db, seeded_db):
    mine, other, fn = _setup(app, db, seeded_db)
    _login(client, "lena@test.ch")
    # Past the rights check: the empty body is what is wrong now.
    assert client.patch(f"/api/v1/mail/groups/{mine}/toggle", json={}).status_code == 400
    assert client.patch(f"/api/v1/mail/functions/{fn}/toggle", json={}).status_code == 400
    assert client.get(f"/api/v1/mail/groups/{mine}/aliases").status_code == 200
    assert client.get(f"/api/v1/mail/functions/{fn}/aliases").status_code == 200
    assert client.patch(f"/api/v1/mail/groups/{other}/toggle", json={}).status_code == 403
    assert client.get(f"/api/v1/mail/groups/{other}/aliases").status_code == 403
    # The address's name stays with the club.
    r = client.patch(f"/api/v1/mail/groups/{mine}/prefix", json={"prefix": "info"})
    assert r.status_code == 403
