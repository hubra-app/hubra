"""What the support site (app/support-frontend) needs from the backend:
questions as a third kind of case, links to the site in mails, and the
person's own privacy requests (download the account, delete it)."""

from __future__ import annotations

import json
from unittest.mock import patch

from hubra.core.models.support_case import SupportCase
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant
from hubra.core.services import email, platform_settings

PASSWORD = "password123"


def _user(db, address="solo@test.ch", **kw) -> User:
    user = User(email=address, first_name="Solo", last_name="User", **kw)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, address="solo@test.ch"):
    resp = client.post("/api/v1/auth/login", json={"email": address, "password": PASSWORD})
    assert resp.status_code == 200, resp.get_json()


# ── Questions (the contact form) ──────────────────────────────────────────────


def test_a_question_is_a_case_without_steps_or_votes(client, db):
    user = _user(db)
    _login(client)
    resp = client.post(
        "/api/v1/global/support/cases",
        json={
            "kind": "question",
            "title": "Frage zu den Preisen",
            "description": "Was kostet Hubra für 80 Mitglieder?",
            "steps": "ignored",
            "useCase": "ignored",
            "severity": "blocking",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["kind"] == "question"
    assert body["steps"] is None and body["useCase"] is None
    assert body["severity"] is None
    assert body["votes"] == 0
    case = db.session.get(SupportCase, body["id"])
    assert case.user_id == user.id
    mine = client.get("/api/v1/global/support/cases").get_json()
    assert [c["kind"] for c in mine] == ["question"]


def test_staff_filter_and_counts_know_questions(client, db):
    user = _user(db, is_superadmin=True)
    _login(client)
    client.post(
        "/api/v1/global/support/cases",
        json={"kind": "question", "title": "Hallo", "description": "Eine Frage"},
    )
    resp = client.get("/api/v1/manager/support/cases?kind=question")
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["openCounts"]["question"] == 1
    assert [c["kind"] for c in body["items"]] == ["question"]
    assert body["items"][0]["reporter"]["id"] == user.id


def test_unknown_kind_is_refused(client, db):
    _user(db)
    _login(client)
    resp = client.post(
        "/api/v1/global/support/cases",
        json={"kind": "praise", "title": "x", "description": "y"},
    )
    assert resp.status_code == 400


# ── Links to the support site in mails ────────────────────────────────────────


def test_case_links_point_at_the_support_site_once_set(app, db):
    with app.test_request_context():
        platform_settings.set_many({"support.url": ""})
        db.session.commit()
        # Not set: the club app's feedback page (or nothing without a base URL).
        assert "support" not in email.support_cases_url(7)
        assert email.support_site_url("/kontakt") == ""
        platform_settings.set_many({"support.url": "https://support.hubra.club/"})
        db.session.commit()
        assert email.support_cases_url(7) == "https://support.hubra.club/meine/7"
        assert email.support_cases_url() == "https://support.hubra.club/meine"
        assert email.support_site_url("/kontakt") == "https://support.hubra.club/kontakt"


# ── Download ──────────────────────────────────────────────────────────────────


def test_export_has_the_account_and_no_secrets(client, db):
    user = _user(db, phone="+41 79 000 00 00")
    user.totp_secret = "SECRET-TOTP"
    user.recovery_codes = ["hash1"]
    db.session.add(Tenant(name="FC X", slug="fcx", status="active"))
    db.session.flush()
    tenant = db.session.query(Tenant).filter_by(slug="fcx").one()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant.id, is_owner=True))
    db.session.commit()
    _login(client)
    client.post(
        "/api/v1/global/support/cases",
        json={"kind": "question", "title": "Hallo", "description": "Eine Frage"},
    )

    resp = client.get("/api/v1/global/account/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.headers["Cache-Control"] == "no-store"
    raw = resp.get_data(as_text=True)
    data = json.loads(raw)
    assert data["account"]["email"] == "solo@test.ch"
    assert data["account"]["phone"] == "+41 79 000 00 00"
    assert data["clubs"] == [
        {"name": "FC X", "slug": "fcx", "status": "active", "owner": True, "since": data["clubs"][0]["since"]}
    ]
    assert [c["title"] for c in data["supportCases"]] == ["Hallo"]
    for secret in ("password_hash", "totp_secret", "recovery_codes"):
        assert secret not in data["account"]
    assert "SECRET-TOTP" not in raw
    assert user.password_hash not in raw


def test_export_needs_a_sign_in(client, db):
    assert client.get("/api/v1/global/account/export").status_code == 401


# ── Delete ────────────────────────────────────────────────────────────────────


def test_deletion_is_blocked_while_in_a_club_or_staff(client, db):
    user = _user(db)
    db.session.add(Tenant(name="FC X", slug="fcx", status="active"))
    db.session.flush()
    tenant = db.session.query(Tenant).filter_by(slug="fcx").one()
    db.session.add(UserTenant(user_id=user.id, tenant_id=tenant.id))
    db.session.commit()
    _login(client)

    check = client.get("/api/v1/global/account/deletion").get_json()
    assert check == {"canDelete": False, "blockers": [{"kind": "club", "name": "FC X", "slug": "fcx"}]}
    resp = client.post("/api/v1/global/account/deletion", json={"currentPassword": PASSWORD})
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "ACCOUNT_IN_USE"
    db.session.refresh(user)
    assert user.email == "solo@test.ch"

    db.session.query(UserTenant).delete()
    user.is_superadmin = True
    db.session.commit()
    check = client.get("/api/v1/global/account/deletion").get_json()
    assert check["blockers"] == [{"kind": "platform", "name": "Hubra", "slug": None}]


def test_deletion_needs_the_password(client, db):
    user = _user(db)
    _login(client)
    resp = client.post("/api/v1/global/account/deletion", json={"currentPassword": "wrong"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "INVALID_PASSWORD"
    db.session.refresh(user)
    assert user.is_disabled is False


def test_deleting_anonymises_and_ends_every_sign_in(client, db):
    user = _user(
        db,
        phone="+41 79 000 00 00",
        address_city="Schwyz",
        private_email_verified=True,
    )
    user_id = user.id
    platform_settings.set_many(
        {"mail.relay.host": "mail.example", "mail.system.sender_email": "noreply@hubra.example"}
    )
    db.session.commit()
    _login(client)
    client.post(
        "/api/v1/global/support/cases",
        json={"kind": "question", "title": "Hallo", "description": "Eine Frage"},
    )
    assert client.get("/api/v1/global/account/deletion").get_json()["canDelete"] is True

    with patch.object(email, "_deliver") as deliver:
        resp = client.post("/api/v1/global/account/deletion", json={"currentPassword": PASSWORD})
    assert resp.status_code == 204, resp.get_data(as_text=True)
    # The confirmation goes to the old address.
    assert deliver.call_args.args[2] == "solo@test.ch"

    db.session.expire_all()
    user = db.session.get(User, user_id)
    assert user.email == f"deleted-{user_id}@deleted.invalid"
    assert user.name == "Gelöschtes Konto"
    assert user.phone is None and user.address_city is None
    assert user.is_disabled is True
    assert user.check_password(PASSWORD) is False
    # The case stays, without the person's name on it.
    case = db.session.query(SupportCase).filter_by(user_id=user_id).one()
    assert case.title == "Hallo"
    assert db.session.query(GlobalAuditEntry).filter_by(action="account_deleted").count() == 1

    # The old session no longer works, and the old address can't sign in.
    assert client.get("/api/v1/global/account/profile").status_code == 401
    resp = client.post("/api/v1/auth/login", json={"email": "solo@test.ch", "password": PASSWORD})
    assert resp.status_code in (400, 401)


# ── Reports without an account ────────────────────────────────────────────────


def _guest(**extra):
    return {
        "email": "Someone@Example.org",
        "name": "Some One",
        "reason": "wrong_recipient",
        "title": "Got a mail for someone else",
        "description": "An invoice for a member I don't know.",
        "mail": "invoice_generated",
        **extra,
    }


def test_a_guest_reports_a_mail_without_signing_in(client, db):
    with patch("hubra.core.services.support.alert_staff"):
        res = client.post("/api/v1/global/support/guest-cases", json=_guest())
    assert res.status_code == 201, res.get_json()
    assert res.get_json() == {"ok": True}
    case = db.session.query(SupportCase).one()
    assert case.user_id is None and case.tenant_id is None
    assert case.kind == "bug" and case.area == "mail"
    assert case.details["guest"] == {
        "email": "someone@example.org",
        "name": "Some One",
        "reason": "wrong_recipient",
        "mail": "invoice_generated",
    }
    from hubra.core.services import support

    assert support.staff_detail(case)["reporter"]["guest"] is True


def test_a_guest_report_needs_an_address_and_the_honeypot_stores_nothing(client, db):
    res = client.post("/api/v1/global/support/guest-cases", json=_guest(email="nope"))
    assert res.status_code == 400
    res = client.post("/api/v1/global/support/guest-cases", json=_guest(kind="feature"))
    assert res.status_code == 400
    res = client.post("/api/v1/global/support/guest-cases", json=_guest(website="spam"))
    assert res.status_code == 201
    assert db.session.query(SupportCase).count() == 0


def test_staff_answers_reach_the_guest_by_mail(app, db):
    from hubra.core.services import support

    with app.test_request_context():
        case = support.submit_guest(_guest())
        db.session.commit()
        with patch.object(email, "send_support_case_update", return_value=True) as send:
            assert support.mail_update(case, support.followers(case), comment="Thanks") == 1
    args, kwargs = send.call_args
    assert args[0] == "someone@example.org"
    assert kwargs["comment"] == "Thanks"
    assert kwargs["with_link"] is False


def test_export_all_has_the_account_and_each_clubs_data(client, db, seeded_db):
    import io
    import zipfile

    from sqlalchemy import select

    from hubra.core.models.data_request import DataRequest

    admin = seeded_db["admin"]
    club = Tenant(name="FC X", slug="fcx", status="active")
    gone = Tenant(name="Old", slug="old", status="suspended")
    db.session.add_all([club, gone])
    db.session.flush()
    db.session.add_all(
        [
            UserTenant(user_id=admin.user_id, tenant_id=club.id, is_owner=True),
            UserTenant(user_id=admin.user_id, tenant_id=gone.id),
        ]
    )
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    with patch("hubra.core.tenant.context.set_search_path"):
        resp = client.get("/api/v1/global/account/export/all")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    assert resp.headers["Content-Type"] == "application/zip"
    assert resp.headers["Cache-Control"] == "no-store"
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    names = set(zf.namelist())
    # Only active clubs; the suspended one is left out.
    assert {"account.json", "README.txt", "clubs/fcx.json"} <= names
    assert "clubs/old.json" not in names
    account = json.loads(zf.read("account.json"))
    assert account["account"]["email"] == "admin@test.ch"
    assert json.loads(zf.read("clubs/fcx.json"))
    # Recorded like a download in the club.
    req = db.session.scalar(select(DataRequest).where(DataRequest.tenant_id == club.id))
    assert req is not None and req.kind == "export" and req.status == "done"


def test_export_all_needs_a_sign_in(client, db):
    assert client.get("/api/v1/global/account/export/all").status_code == 401
