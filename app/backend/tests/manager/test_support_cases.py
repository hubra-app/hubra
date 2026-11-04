"""Problem reports and feature requests: sent from the app, handled by
platform staff in manage › Support, ideas on the public roadmap."""

from __future__ import annotations

from email import message_from_string
from unittest.mock import patch

import pytest

from hubra.core.models.support_case import SupportCase, SupportCaseVote
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.user import User
from hubra.core.services import email, platform_settings

CLUB = {"X-Tenant-Slug": "club-a"}
STAFF = "/api/v1/manager/support/cases"

FINGERPRINT = {
    "browser": "Firefox",
    "browserVersion": "132.0",
    "os": "Android",
    "osVersion": "14",
    "deviceType": "phone",
    "screenWidth": 412,
    "screenHeight": 915,
    "viewportWidth": 412,
    "viewportHeight": 800,
    "language": "de-CH",
    "theme": "dark",
    # Not on the list: dropped.
    "userAgent": "Mozilla/5.0 (Linux; Android 14) ...",
    "ip": "10.0.0.1",
    "canvasHash": "abc",
}


@pytest.fixture
def deliver():
    with patch.object(email, "_deliver") as d:
        yield d


def _seed_mail_texts(db) -> None:
    import json
    from pathlib import Path

    from hubra.core.models.translation import Translation

    seeds = Path(__file__).resolve().parents[2] / "hubra/core/seed_data/translations"
    texts = json.loads((seeds / "de-CH.json").read_text(encoding="utf-8"))
    for key, value in texts.items():
        if key.startswith("mail.email."):
            db.session.add(Translation(locale="de-CH", key=key, value=value))


@pytest.fixture
def club(client, db, seeded_db):
    db.session.add(Tenant(name="Club A", slug="club-a", status="active"))
    _seed_mail_texts(db)
    platform_settings.set_many(
        {
            "mail.relay.host": "mail.example",
            "mail.system.sender_email": "noreply@hubra.example",
        }
    )
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers=CLUB,
    )
    return seeded_db


def _report(client, **body):
    payload = {
        "kind": "bug",
        "title": "Rechnung lässt sich nicht speichern",
        "description": "Beim Speichern kommt ein Fehler.",
        "steps": "1. Finanzen\n2. Neue Rechnung\n3. Speichern",
        "expected": "Die Rechnung ist gespeichert.",
        "severity": "blocking",
        "area": "finance",
        "page": "/app/finances/invoices?page=2#top",
        "fingerprint": FINGERPRINT,
    } | body
    return client.post("/api/v1/support/cases", json=payload, headers=CLUB)


def _staff(club, db):
    club["user"].is_superadmin = True
    db.session.commit()


def _mails(deliver) -> list[tuple[str, str, str]]:
    """(recipient, subject, plain text) of each mail handed to the relay."""
    from email.header import decode_header, make_header

    out = []
    for c in deliver.call_args_list:
        msg = message_from_string(c.args[3])
        subject = str(make_header(decode_header(msg["Subject"])))
        text = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
        out.append((c.args[2], subject, text.get_payload(decode=True).decode()))
    return out


def _subjects(deliver) -> list[str]:
    return [m[1] for m in _mails(deliver)]


def _user(db, email_address: str) -> User:
    user = User(
        email=email_address,
        first_name="B",
        last_name="Bee",
        private_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    return user


def test_a_problem_report_keeps_only_the_device_fields(client, club, db, deliver):
    resp = _report(client)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "open"
    assert body["steps"].startswith("1. Finanzen")
    assert body["page"] == "/app/finances/invoices"
    assert set(body["fingerprint"]) == {
        "browser",
        "browserVersion",
        "os",
        "osVersion",
        "deviceType",
        "screenWidth",
        "screenHeight",
        "viewportWidth",
        "viewportHeight",
        "language",
        "theme",
        "appVersion",
    }
    case = db.session.get(SupportCase, body["id"])
    assert case.tenant_id is not None
    assert "userAgent" not in case.fingerprint

    mine = client.get("/api/v1/support/cases", headers=CLUB).get_json()
    assert [c["id"] for c in mine] == [body["id"]]


def test_platform_admins_get_an_alert_for_a_new_case(client, club, db, deliver):
    _staff(club, db)
    _report(client)
    mails = _mails(deliver)
    assert any(
        "New problem report" in subject and "Firefox 132.0 on Android (phone)" in text
        for _to, subject, text in mails
    ), mails


def test_the_form_needs_a_title_and_a_description(client, club):
    assert _report(client, title="  ").status_code == 400
    assert _report(client, description="").status_code == 400
    assert _report(client, kind="praise").status_code == 400
    assert _report(client, severity="urgent").status_code == 400
    assert _report(client, title="x" * 201).status_code == 400


def test_a_feature_request_counts_its_reporters_vote(client, club, db):
    resp = _report(
        client,
        kind="feature",
        title="Dunkler Kalender",
        description="Der Kalender im dunklen Modus",
        useCase="Abends lesen",
        severity="blocking",
    )
    body = resp.get_json()
    assert body["useCase"] == "Abends lesen"
    assert body["severity"] is None
    assert body["votes"] == 1


def test_others_never_see_a_case(client, club, db):
    case_id = _report(client).get_json()["id"]
    other = User(
        email="other@test.ch",
        first_name="O",
        last_name="Ther",
        private_email_verified=True,
    )
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login", json={"email": "other@test.ch", "password": "password123"}
    )
    assert client.get(f"/api/v1/support/cases/{case_id}").status_code == 404
    assert client.get("/api/v1/support/cases").get_json() == []


def test_a_club_admin_cannot_open_the_staff_view(client, club):
    _report(client)
    assert client.get(STAFF).status_code == 403


def test_staff_list_filter_and_counts(client, club, db):
    _report(client)
    _report(client, kind="feature", title="Idee", description="Etwas Neues")
    _staff(club, db)
    data = client.get(f"{STAFF}?status=active").get_json()
    assert data["total"] == 2
    assert data["openCounts"] == {"bug": 1, "feature": 1, "question": 0}
    first = data["items"][0]
    assert first["reporter"]["email"] == "admin@test.ch"
    assert first["club"]["name"] == "Club A"

    bugs = client.get(f"{STAFF}?kind=bug").get_json()
    assert [i["kind"] for i in bugs["items"]] == ["bug"]
    found = client.get(f"{STAFF}?q=idee").get_json()
    assert [i["title"] for i in found["items"]] == ["Idee"]
    assert client.get(f"{STAFF}?status=nope").status_code == 400


def test_staff_answer_reaches_the_reporter_but_notes_do_not(client, club, db, deliver):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    deliver.reset_mock()

    resp = client.post(
        f"{STAFF}/{case_id}/comments", json={"body": "Danke, wir schauen es an."}
    )
    assert resp.status_code == 201
    ((to, subject, text),) = _mails(deliver)
    assert to == "admin@test.ch"
    assert (
        subject
        == f"[Hubra] Deine Meldung #{case_id}: Rechnung lässt sich nicht speichern"
    )
    assert "Danke, wir schauen es an." in text
    assert "[mail." not in text

    deliver.reset_mock()
    client.post(
        f"{STAFF}/{case_id}/comments", json={"body": "Wohl der Cache", "internal": True}
    )
    assert deliver.call_count == 0

    seen = client.get(f"/api/v1/support/cases/{case_id}", headers=CLUB).get_json()
    assert [c["body"] for c in seen["comments"]] == ["Danke, wir schauen es an."]
    assert seen["comments"][0]["fromStaff"] is True
    assert seen["comments"][0]["author"] is None  # shown as the Hubra team

    full = client.get(f"{STAFF}/{case_id}").get_json()
    assert [c["internal"] for c in full["comments"]] == [False, True]


def test_the_reporter_replies_and_the_case_waits_on_staff(client, club, db):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    client.post(f"{STAFF}/{case_id}/comments", json={"body": "Welcher Browser?"})
    resp = client.post(
        f"/api/v1/support/cases/{case_id}/comments",
        json={"body": "Firefox"},
        headers=CLUB,
    )
    assert resp.status_code == 201
    item = client.get(STAFF).get_json()["items"][0]
    assert item["awaitingReply"] is True


def test_closing_mails_the_reporter_and_is_audited(client, club, db, deliver):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    deliver.reset_mock()
    resp = client.patch(f"{STAFF}/{case_id}", json={"status": "done"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["closedAt"]
    assert deliver.call_count == 1
    entry = (
        db.session.query(GlobalAuditEntry).filter_by(action="support_case.update").one()
    )
    assert entry.details["status"] == {"from": "open", "to": "done"}

    deliver.reset_mock()
    client.patch(f"{STAFF}/{case_id}", json={"status": "open", "notify": False})
    assert deliver.call_count == 0
    assert client.get(f"{STAFF}/{case_id}").get_json()["closedAt"] is None
    assert (
        client.patch(f"{STAFF}/{case_id}", json={"status": "nope"}).status_code == 400
    )


def _ideas(resp) -> list[dict]:
    """The ideas on the one roadmap (planned items left out)."""
    return [i for i in resp.get_json()["items"] if i["source"] == "idea"]


def test_only_feature_requests_go_on_the_roadmap(client, club, db):
    bug = _report(client).get_json()["id"]
    idea = _report(client, kind="feature", title="Idee", description="Neu").get_json()[
        "id"
    ]
    _staff(club, db)
    assert client.patch(f"{STAFF}/{bug}", json={"isPublic": True}).status_code == 400

    assert _ideas(client.get("/api/v1/roadmap")) == []
    client.patch(
        f"{STAFF}/{idea}",
        json={"isPublic": True, "status": "planned", "title": "Neue Idee"},
    )
    public = _ideas(client.get("/api/v1/roadmap"))
    assert public == [
        {
            "id": f"idea-{idea}",
            "caseId": idea,
            "source": "idea",
            # "planned" shows under "later" on the one roadmap.
            "status": "later",
            "area": {"de": "Finanzen", "en": "Finance"},
            "title": {"de": "Neue Idee", "en": "Neue Idee"},
            "summary": {"de": "Neu", "en": "Neu"},
            "version": None,
            "link": None,
            "votes": 1,
            "voteable": True,
            "createdAt": public[0]["createdAt"],
        }
    ]
    # The same list on the What's new endpoint and for the website.
    assert _ideas(client.get("/api/v1/version/roadmap")) == public
    site = client.get("/api/v1/public/roadmap", headers={"Origin": "https://hubra.club"})
    assert _ideas(site) == public
    assert site.headers["Access-Control-Allow-Origin"] == "*"


def test_the_public_roadmap_needs_no_sign_in(client, club, db):
    idea = _report(client, kind="feature", title="Idee", description="Neu").get_json()[
        "id"
    ]
    _staff(club, db)
    client.patch(f"{STAFF}/{idea}", json={"isPublic": True})
    client.post("/api/v1/auth/logout")
    client.delete_cookie("access_token_cookie")
    fresh = client.application.test_client()
    resp = fresh.get("/api/v1/roadmap")
    assert resp.status_code == 200
    ideas = _ideas(resp)
    assert [i["caseId"] for i in ideas] == [idea]
    assert "reporter" not in ideas[0] and "voted" not in ideas[0]


def test_votes_on_the_roadmap(client, club, db):
    idea = _report(client, kind="feature", title="Idee", description="Neu").get_json()[
        "id"
    ]
    bug = _report(client).get_json()["id"]
    _staff(club, db)
    # Not public yet.
    assert client.post(f"/api/v1/support/roadmap/{idea}/vote").status_code == 404
    client.patch(f"{STAFF}/{idea}", json={"isPublic": True})

    items = _ideas(client.get("/api/v1/support/roadmap", headers=CLUB))
    assert items[0]["voted"] is True and items[0]["votes"] == 1
    resp = client.delete(f"/api/v1/support/roadmap/{idea}/vote", headers=CLUB)
    assert resp.get_json() == {"id": idea, "votes": 0, "voted": False}
    resp = client.post(f"/api/v1/support/roadmap/{idea}/vote", headers=CLUB)
    assert resp.get_json()["votes"] == 1
    # Twice is still one vote.
    assert client.post(f"/api/v1/support/roadmap/{idea}/vote").get_json()["votes"] == 1
    assert client.post(f"/api/v1/support/roadmap/{bug}/vote").status_code == 404


def test_merging_moves_votes_and_closes_the_duplicate(client, club, db, deliver):
    target = _report(
        client, kind="feature", title="Kalender-Abo", description="ics"
    ).get_json()["id"]
    other = _user(db, "b@test.ch")
    dup = SupportCase(
        kind="feature", title="Kalender in Outlook", description="Abo", user_id=other.id
    )
    db.session.add(dup)
    db.session.flush()
    db.session.add(SupportCaseVote(case_id=dup.id, user_id=other.id))
    db.session.commit()
    dup_id = dup.id
    bug = _report(client).get_json()["id"]
    _staff(club, db)
    deliver.reset_mock()

    assert client.post(f"{STAFF}/{dup_id}/merge", json={"into": bug}).status_code == 400
    assert (
        client.post(f"{STAFF}/{dup_id}/merge", json={"into": dup_id}).status_code == 400
    )

    resp = client.post(f"{STAFF}/{dup_id}/merge", json={"into": target})
    assert resp.status_code == 200, resp.get_json()
    merged = resp.get_json()
    assert merged["id"] == target
    assert merged["votes"] == 2
    assert [m["id"] for m in merged["merged"]] == [dup_id]
    assert merged["comments"][-1]["internal"] is True

    source = client.get(f"{STAFF}/{dup_id}").get_json()
    assert source["status"] == "closed"
    assert source["mergedInto"]["id"] == target
    assert [m[0] for m in _mails(deliver)] == ["b@test.ch"]

    # Merged cases stay closed and cannot be merged again.
    assert client.patch(f"{STAFF}/{dup_id}", json={"status": "open"}).status_code == 400
    assert (
        client.post(f"{STAFF}/{dup_id}/merge", json={"into": target}).status_code == 400
    )


def test_a_status_change_reaches_the_reporters_of_merged_cases(
    client, club, db, deliver
):
    target = _report(client, kind="feature", title="A", description="a").get_json()[
        "id"
    ]
    other = _user(db, "c@test.ch")
    dup = SupportCase(kind="feature", title="B", description="b", user_id=other.id)
    db.session.add(dup)
    db.session.commit()
    dup_id = dup.id
    _staff(club, db)
    client.post(f"{STAFF}/{dup_id}/merge", json={"into": target})
    deliver.reset_mock()
    client.patch(f"{STAFF}/{target}", json={"status": "in_progress"})
    recipients = sorted(m[0] for m in _mails(deliver))
    assert recipients == ["admin@test.ch", "c@test.ch"]


def test_support_role_holders_handle_cases(client, club, db):
    from hubra.core.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import GlobalRole, UserGlobalRole

    case_id = _report(client).get_json()["id"]
    seed_global_rbac()
    role = db.session.query(GlobalRole).filter_by(name="Support").one()
    db.session.add(UserGlobalRole(user_id=club["user"].id, role_id=role.id))
    db.session.commit()
    with patch("hubra.core.permissions.staff_mfa_missing", return_value=False):
        assert client.get(f"{STAFF}/{case_id}").status_code == 200
        assert (
            client.patch(f"{STAFF}/{case_id}", json={"status": "closed"}).status_code
            == 200
        )


PLAN = [
    {
        "id": "twint",
        "status": "next",
        "area": {"de": "Finanzen", "en": "Finance"},
        "title": {"de": "TWINT", "en": "TWINT"},
        "summary": {},
        "version": None,
        "link": None,
    },
    {
        "id": "shipped",
        "status": "done",
        "area": {},
        "title": {"de": "Fertig", "en": "Shipped"},
        "summary": {},
        "version": "0.6.0",
        "link": None,
    },
]


@pytest.fixture
def plan(monkeypatch):
    from hubra.core.services import support as services

    monkeypatch.setattr(services, "_plan", lambda: [dict(p) for p in PLAN])
    return PLAN


def _items(resp) -> dict[str, dict]:
    return {i["id"]: i for i in resp.get_json()["items"]}


def test_the_roadmap_shows_planned_items_and_ideas_in_one_list(client, club, db, plan):
    idea = _report(
        client, kind="feature", title="Modul Fahrdienst", description="x", area="modules"
    ).get_json()["id"]
    _staff(club, db)
    client.patch(f"{STAFF}/{idea}", json={"isPublic": True})

    items = _items(client.get("/api/v1/version/roadmap"))
    assert list(items) == ["twint", "shipped", f"idea-{idea}"]
    assert items["twint"]["source"] == "plan" and items["twint"]["voteable"] is True
    assert items["shipped"]["voteable"] is False
    assert items[f"idea-{idea}"]["status"] == "idea"
    assert items[f"idea-{idea}"]["area"] == {"de": "Modul", "en": "Module"}


def test_a_linked_idea_counts_for_the_planned_item(client, club, db, plan):
    idea = _report(client, kind="feature", title="TWINT bitte", description="x").get_json()[
        "id"
    ]
    _staff(club, db)
    assert (
        client.patch(f"{STAFF}/{idea}", json={"roadmapItem": "nope"}).status_code == 400
    )
    resp = client.patch(f"{STAFF}/{idea}", json={"roadmapItem": "twint"})
    assert resp.get_json()["roadmapItem"] == "twint"

    items = _items(client.get("/api/v1/support/roadmap", headers=CLUB))
    # Shown as the planned item, not on its own; the reporter's vote counts.
    assert f"idea-{idea}" not in items
    assert items["twint"]["votes"] == 1 and items["twint"]["voted"] is True
    assert items["twint"]["ideas"] == 1

    # Voting again for the item is still one person.
    url = "/api/v1/support/roadmap/items/twint/vote"
    assert client.post(url, headers=CLUB).get_json()["votes"] == 1
    other = _user(db, "b@test.ch")
    db.session.add(SupportCaseVote(case_id=idea, user_id=other.id))
    db.session.commit()
    assert _items(client.get("/api/v1/roadmap"))["twint"]["votes"] == 2
    # Taking the vote back removes it from the linked idea too.
    assert client.delete(url, headers=CLUB).get_json()["votes"] == 1


def test_votes_for_planned_items(client, club, db, plan):
    url = "/api/v1/support/roadmap/items/{}/vote"
    resp = client.post(url.format("twint"), headers=CLUB)
    assert resp.get_json() == {"id": "twint", "votes": 1, "voted": True}
    assert client.post(url.format("twint"), headers=CLUB).get_json()["votes"] == 1
    # Already shipped: no more votes.
    assert client.post(url.format("shipped"), headers=CLUB).status_code == 409
    assert client.post(url.format("missing"), headers=CLUB).status_code == 404
    items = _items(client.get("/api/v1/support/roadmap", headers=CLUB))
    assert items["twint"]["voted"] is True
    assert client.delete(url.format("twint"), headers=CLUB).get_json()["votes"] == 0


def test_staff_filter_by_area(client, club, db):
    _report(client)
    mod = _report(
        client, kind="feature", title="Modul", description="x", area="modules"
    ).get_json()["id"]
    _staff(club, db)
    body = client.get(f"{STAFF}?area=modules").get_json()
    assert [c["id"] for c in body["items"]] == [mod]
    assert client.get(f"{STAFF}?area=nope").status_code == 400
