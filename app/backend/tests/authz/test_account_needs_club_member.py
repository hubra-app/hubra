"""Account routes on one club's data refuse a sign-in without a club.

A sign-in on the SSO portal is a User; its id is not a member id. Those
routes used it as one, inside whatever club the request named, and so read
or changed the club member that happened to have the same number.
"""

from datetime import date

import pytest
from flask_jwt_extended import create_access_token

from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.models.user import User

CLUB_MEMBER_ROUTES = [
    ("GET", "/api/v1/account/invoices"),
    ("GET", "/api/v1/account/groups"),
    ("GET", "/api/v1/account/mail-settings"),
    ("PATCH", "/api/v1/account/mail-settings"),
    ("GET", "/api/v1/account/sessions"),
    ("POST", "/api/v1/account/sessions/revoke-all"),
    ("GET", "/api/v1/account/devices"),
]


@pytest.fixture
def outsider_with_namesake(app, client, db, seeded_db):
    """A user with no member profile, and a member whose id is that user's id."""
    outsider = User(email="outsider@test.ch", first_name="Out", last_name="Sider")
    outsider.set_password("password123")
    db.session.add(outsider)
    db.session.flush()

    other = User(email="other@test.ch", first_name="Other", last_name="Member")
    other.set_password("password123")
    db.session.add(other)
    db.session.flush()
    namesake = Member(
        id=outsider.id, user_id=other.id, status="active", tier_id=seeded_db["tier"].id
    )
    db.session.add(namesake)
    db.session.flush()
    db.session.add(
        Invoice(
            member_id=namesake.id,
            issued=date(2026, 1, 1),
            due=date(2026, 2, 1),
            amount=123,
            status="Open",
        )
    )
    db.session.commit()

    with app.app_context():
        token = create_access_token(identity=f"user:{outsider.id}")
    client.set_cookie("access_token_cookie", token)
    return outsider


@pytest.mark.parametrize("method,url", CLUB_MEMBER_ROUTES)
def test_user_without_a_club_is_refused(client, outsider_with_namesake, method, url):
    resp = client.open(url, method=method, json={"forwarding_enabled": False})
    assert resp.status_code == 403, resp.get_data(as_text=True)


def test_user_without_a_club_still_has_the_account_page(client, outsider_with_namesake):
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "outsider@test.ch"


def test_member_still_reads_their_own(client, auth_headers):
    for url in ("/api/v1/account/invoices", "/api/v1/account/sessions"):
        assert client.get(url, headers=auth_headers).status_code == 200, url


def test_qr_bill_for_a_user_without_a_club_is_403(client, db, outsider_with_namesake):
    invoice = db.session.query(Invoice).filter_by(member_id=outsider_with_namesake.id).one()
    resp = client.get(f"/api/v1/finance/invoices/{invoice.id}/qr-bill.pdf")
    assert resp.status_code == 403


def test_translations_record_the_member_not_the_user(app, client, db, seeded_db):
    """With an account sign-in, the editor is the club member of that account
    (its id differs from the account's id)."""
    from hubra.core.models.translation import Translation

    user = User(email="editor@test.ch", first_name="Edi", last_name="Tor")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    member = Member(id=user.id + 500, user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    member.roles = [seeded_db["role"]]
    db.session.add(member)
    db.session.commit()
    with app.app_context():
        client.set_cookie("access_token_cookie", create_access_token(identity=f"user:{user.id}"))

    resp = client.patch("/api/v1/i18n/de", json=[{"key": "x.hello", "value": "Hallo"}])
    assert resp.status_code == 200, resp.get_data(as_text=True)

    row = db.session.query(Translation).filter_by(key="x.hello").one()
    assert row.updated_by_id == member.id
