"""Support cases on Discord: a private thread per case, its messages as
comments, and more people on a case (``services.support_discord``)."""

from __future__ import annotations

import pytest

from hubra.core.models.connected_app import ExternalAccount
from hubra.core.models.support_case import (
    SupportCase,
    SupportCaseComment,
    SupportCasePerson,
)
from hubra.core.services import platform_bot, platform_discord, platform_settings
from hubra.core.services import support_discord
from hubra.core.services.platform_bot import BotError

from tests.manager import test_support_cases as base
from tests.manager.test_support_cases import (
    CLUB,
    STAFF,
    _mails,
    _report,
    _staff,
    _user,
)

# The fixtures of the support case tests.
club = base.club
deliver = base.deliver

CHANNEL, GUILD, THREAD = "500", "42", "700"


class FakeDiscord:
    """Answers the bot's calls like Discord would."""

    def __init__(self):
        self.calls: list[tuple[str, str, object]] = []
        self.members: set[str] = set()
        self.messages: list[dict] = []
        self.next_id = 1000

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and path == f"/channels/{CHANNEL}":
            return {"guild_id": GUILD}
        if method == "POST" and path == f"/channels/{CHANNEL}/threads":
            return {"id": THREAD}
        if method == "POST" and path.endswith("/messages"):
            self.next_id += 1
            return {"id": str(self.next_id)}
        if method == "GET" and path.startswith(f"/guilds/{GUILD}/members/"):
            if path.rsplit("/", 1)[1] in self.members:
                return {"user": {}}
            raise BotError("Discord answered 404", 404)
        if method == "POST" and path == f"/channels/{CHANNEL}/invites":
            return {"code": "joinus"}
        if method == "GET" and path == f"/guilds/{GUILD}/threads/active":
            newest = self.messages[-1]["id"] if self.messages else None
            return {
                "threads": [
                    {"id": THREAD, "parent_id": CHANNEL, "last_message_id": newest},
                    {"id": "999", "parent_id": "other", "last_message_id": "1"},
                ]
            }
        if method == "GET" and path.startswith(f"/channels/{THREAD}/messages"):
            after = int(path.split("after=")[1].split("&")[0])
            return [m for m in self.messages if int(m["id"]) > after]
        if method in ("PUT", "PATCH", "DELETE"):
            return None
        raise AssertionError(f"unexpected call {method} {path}")

    def paths(self, method: str) -> list[str]:
        return [p for m, p, _ in self.calls if m == method]

    def say(self, author_id: str, content: str, *, bot: bool = False) -> None:
        self.next_id += 1
        self.messages.append(
            {
                "id": str(self.next_id),
                "type": 0,
                "content": content,
                "author": {"id": author_id, "username": f"u{author_id}", "bot": bot},
            }
        )


@pytest.fixture
def discord(monkeypatch, db):
    fake = FakeDiscord()
    monkeypatch.setattr(platform_bot, "_redis", lambda: None)
    monkeypatch.setattr(platform_bot, "_local", {})
    monkeypatch.setattr(platform_bot, "_token", lambda: "bot-token")
    monkeypatch.setattr(platform_bot, "_bot", fake)
    fake.dms = []
    monkeypatch.setattr(
        platform_discord,
        "dm",
        lambda user, embed, components=None: fake.dms.append((user, embed, components))
        or {"id": "1"},
    )
    platform_settings.set_many({support_discord.CHANNEL_KEY: CHANNEL})
    db.session.commit()

    # Celery's eager tasks run in an app of their own (another database):
    # run the jobs here, and let their errors fail the test.
    from hubra.core.tasks import support_discord_tasks as tasks

    def run_now(name, *args):
        if not support_discord.enabled():
            return
        monkeypatch.setattr(tasks, "_run", lambda _n, fn, *a: fn(*a))
        getattr(tasks, name).run(*args)

    monkeypatch.setattr(support_discord, "_queue", run_now)
    return fake


def _link(db, user, discord_id: str) -> None:
    db.session.add(
        ExternalAccount(user_id=user.id, provider="discord", external_id=discord_id)
    )
    db.session.commit()


def test_a_new_case_gets_a_thread_and_its_reporter(client, club, db, discord):
    _link(db, club["user"], "900")
    discord.members.add("900")
    case_id = _report(client).get_json()["id"]

    case = db.session.get(SupportCase, case_id)
    assert case.discord_thread_id == THREAD
    method, path, body = discord.calls[0]
    assert (method, path) == ("POST", f"/channels/{CHANNEL}/threads")
    assert body["type"] == 12 and body["invitable"] is False
    assert body["name"].startswith(f"#{case_id} ")
    starter = next(b for m, p, b in discord.calls if p.endswith("/messages"))
    embed = starter["embeds"][0]
    assert embed["title"].startswith(f"#{case_id} Rechnung")
    # Never the reporter's e-mail address.
    assert "admin@test.ch" not in str(starter)
    assert case.discord_last_message_id == "1001"

    assert f"/channels/{THREAD}/thread-members/900" in discord.paths("PUT")
    row = db.session.query(SupportCasePerson).one()
    assert (row.user_id, row.discord) == (club["user"].id, "added")


def test_reporters_off_the_server_get_an_invite(client, club, db, discord):
    _link(db, club["user"], "900")
    case_id = _report(client).get_json()["id"]

    row = db.session.query(SupportCasePerson).one()
    assert (row.discord, row.invite_code) == ("invited", "joinus")
    ((to, embed, components),) = discord.dms
    assert to == "900"
    assert components[0]["components"][0]["url"] == "https://discord.gg/joinus"
    assert discord.paths("PUT") == []

    # They join the server: the tick puts them in the thread.
    discord.members.add("900")
    support_discord.sync()
    db.session.refresh(row)
    assert row.discord == "added" and row.invite_code is None
    assert f"/channels/{THREAD}/thread-members/900" in discord.paths("PUT")
    # Only one invite.
    assert len(discord.dms) == 1
    _staff(club, db)
    staff_view = client.get(f"{STAFF}/{case_id}").get_json()
    assert staff_view["people"][0]["discord"] == "added"


def test_without_linked_discord_nothing_is_sent(client, club, db, discord):
    _report(client)
    row = db.session.query(SupportCasePerson).one()
    assert row.discord == "no_discord"
    assert discord.dms == [] and discord.paths("PUT") == []


def test_reporters_stay_out_when_the_setting_is_off(client, club, db, discord):
    platform_settings.set_many({support_discord.ADD_REPORTERS_KEY: "off"})
    db.session.commit()
    _link(db, club["user"], "900")
    discord.members.add("900")
    _report(client)
    assert db.session.query(SupportCasePerson).count() == 0
    assert discord.paths("PUT") == []


def test_comments_from_hubra_go_into_the_thread(client, club, db, discord):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    discord.calls.clear()

    client.post(f"{STAFF}/{case_id}/comments", json={"body": "Wir schauen es an."})
    client.post(
        f"{STAFF}/{case_id}/comments", json={"body": "Cache?", "internal": True}
    )
    client.post(
        f"/api/v1/support/cases/{case_id}/comments",
        json={"body": "Danke!"},
        headers=CLUB,
    )
    posted = [b["content"] for m, p, b in discord.calls if p.endswith("/messages")]
    assert len(posted) == 2
    assert posted[0].endswith("· Team\nWir schauen es an.")
    assert posted[1].endswith("· meldende Person\nDanke!")
    stored = db.session.query(SupportCaseComment).order_by(SupportCaseComment.id).all()
    assert [c.discord_message_id is not None for c in stored] == [True, False, True]


def test_thread_messages_become_comments(client, club, db, discord, deliver):
    _link(db, club["user"], "900")
    case_id = _report(client).get_json()["id"]  # reporter invited, not in thread
    helper = _user(db, "staff@test.ch")
    helper.is_superadmin = True
    stranger = _user(db, "stranger@test.ch")
    db.session.commit()
    _link(db, helper, "800")
    _link(db, stranger, "700700")

    discord.say("800", "Ist behoben, bitte nochmals versuchen.")
    discord.say("800", "// lag am Cache")
    discord.say("900", "Geht jetzt, danke!")
    discord.say("700700", "Hab ich auch gesehen")
    discord.say("1", "Ich bin ein Bot", bot=True)
    deliver.reset_mock()
    support_discord.sync()

    rows = (
        db.session.query(SupportCaseComment)
        .filter_by(case_id=case_id)
        .order_by(SupportCaseComment.id)
        .all()
    )
    assert [(c.body, c.from_staff, c.internal) for c in rows] == [
        ("Ist behoben, bitte nochmals versuchen.", True, False),
        ("lag am Cache", True, True),
        ("Geht jetzt, danke!", False, False),
        ("B Bee (Discord): Hab ich auch gesehen", True, True),
    ]
    assert rows[2].user_id == club["user"].id
    # The reporter is not in the thread yet: the answer comes by mail.
    ((to, _subject, text),) = _mails(deliver)
    assert to == "admin@test.ch" and "Ist behoben" in text

    # Read once only.
    platform_bot._local.clear()
    support_discord.sync()
    assert db.session.query(SupportCaseComment).filter_by(case_id=case_id).count() == 4


def test_answers_skip_mail_for_people_in_the_thread(client, club, db, discord, deliver):
    _link(db, club["user"], "900")
    discord.members.add("900")
    _report(client)
    helper = _user(db, "staff@test.ch")
    helper.is_superadmin = True
    db.session.commit()
    _link(db, helper, "800")
    discord.say("800", "Schon erledigt")
    deliver.reset_mock()
    support_discord.sync()
    assert deliver.call_count == 0


def test_staff_add_several_people(client, club, db, discord, deliver):
    case_id = _report(client).get_json()["id"]
    anna = _user(db, "anna@test.ch")
    ben = _user(db, "ben@test.ch")
    db.session.commit()
    _link(db, anna, "111")
    discord.members.add("111")
    _staff(club, db)

    found = client.get("/api/v1/manager/support/accounts?q=anna").get_json()
    assert [a["email"] for a in found["items"]] == ["anna@test.ch"]

    resp = client.post(
        f"{STAFF}/{case_id}/people", json={"userIds": [anna.id, ben.id, anna.id]}
    )
    assert resp.status_code == 200, resp.get_json()
    people = {p["email"]: p for p in resp.get_json()["people"]}
    assert people["admin@test.ch"]["reporter"] is True
    assert people["anna@test.ch"]["discord"] == "added"
    assert people["ben@test.ch"]["discord"] == "no_discord"
    assert f"/channels/{THREAD}/thread-members/111" in discord.paths("PUT")

    # They hear about a new status, like the reporter.
    deliver.reset_mock()
    client.patch(f"{STAFF}/{case_id}", json={"status": "in_progress"})
    assert {m[0] for m in _mails(deliver)} == {
        "admin@test.ch",
        "anna@test.ch",
        "ben@test.ch",
    }

    # Taken off again: out of the thread too.
    resp = client.delete(f"{STAFF}/{case_id}/people/{anna.id}")
    assert resp.status_code == 200
    assert f"/channels/{THREAD}/thread-members/111" in discord.paths("DELETE")
    assert client.delete(f"{STAFF}/{case_id}/people/{anna.id}").status_code == 404
    assert client.post(f"{STAFF}/{case_id}/people", json={"userIds": []}).status_code == 400


def test_added_people_see_and_answer_the_case(client, club, db, discord):
    case_id = _report(client).get_json()["id"]
    other = _user(db, "other@test.ch")
    db.session.commit()
    _staff(club, db)
    client.post(f"{STAFF}/{case_id}/people", json={"userIds": [other.id]})

    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login", json={"email": "other@test.ch", "password": "password123"}
    )
    assert [c["id"] for c in client.get("/api/v1/support/cases").get_json()] == [case_id]
    assert client.get(f"/api/v1/support/cases/{case_id}").status_code == 200
    resp = client.post(
        f"/api/v1/support/cases/{case_id}/comments", json={"body": "Bei mir auch"}
    )
    assert resp.status_code == 201
    posted = [b.get("content") for m, p, b in discord.calls if p.endswith("/messages")]
    assert posted[-1].endswith("· beteiligt\nBei mir auch")


def test_finishing_a_case_archives_its_thread(client, club, db, discord):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    discord.calls.clear()
    client.patch(f"{STAFF}/{case_id}", json={"status": "done", "notify": False})
    status = next(b for m, p, b in discord.calls if p.endswith("/messages"))
    assert status["embeds"][0]["description"] == "Status: Erledigt"
    assert ("PATCH", f"/channels/{THREAD}", {"archived": True}) in discord.calls


def test_an_archived_thread_is_opened_before_posting(
    client, club, db, discord, monkeypatch
):
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    real = discord.__class__.__call__
    state = {"archived": True}

    def archived(self, method, path, body=None):
        if path == f"/channels/{THREAD}/messages" and state["archived"]:
            self.calls.append((method, path, body))
            raise BotError("Discord answered 400", 400)
        if method == "PATCH" and body == {"archived": False}:
            state["archived"] = False
        return real(self, method, path, body)

    import types

    monkeypatch.setattr(platform_bot, "_bot", types.MethodType(archived, discord))
    resp = client.post(f"{STAFF}/{case_id}/comments", json={"body": "Noch da?"})
    assert resp.status_code == 201
    assert ("PATCH", f"/channels/{THREAD}", {"archived": False}) in discord.calls
    comment = db.session.query(SupportCaseComment).one()
    assert comment.discord_message_id is not None


def test_older_cases_get_a_thread_on_request(client, club, db, discord):
    platform_settings.set_many({support_discord.CHANNEL_KEY: None})
    db.session.commit()
    case_id = _report(client).get_json()["id"]
    _staff(club, db)
    assert client.post(f"{STAFF}/{case_id}/discord").status_code == 409
    assert discord.calls == []

    platform_settings.set_many({support_discord.CHANNEL_KEY: CHANNEL})
    db.session.commit()
    resp = client.post(f"{STAFF}/{case_id}/discord")
    assert resp.status_code == 202
    detail = client.get(f"{STAFF}/{case_id}").get_json()
    assert detail["discord"]["threadId"] == THREAD
    assert detail["discord"]["threadUrl"] == f"https://discord.com/channels/{GUILD}/{THREAD}"


def test_no_support_channel_means_no_discord(client, club, db, monkeypatch):
    calls = []
    monkeypatch.setattr(platform_bot, "_bot", lambda *a, **k: calls.append(a))
    case_id = _report(client).get_json()["id"]
    assert calls == []
    assert db.session.get(SupportCase, case_id).discord_thread_id is None


def test_threads_follow_the_bot_language(client, club, db, discord):
    platform_settings.set_many({"discord.language": "en"})
    db.session.commit()
    case_id = _report(client).get_json()["id"]
    case = db.session.get(SupportCase, case_id)
    embed = support_discord.starter_embed(case)
    assert embed["fields"][0] == {"name": "Kind", "value": "Problem", "inline": True}
    assert embed["footer"]["text"].startswith("What is written here")
    _staff(club, db)
    discord.calls.clear()
    client.patch(f"{STAFF}/{case_id}", json={"status": "done", "notify": False})
    status = next(b for m, p, b in discord.calls if p.endswith("/messages"))
    assert status["embeds"][0]["description"] == "Status: Done"
