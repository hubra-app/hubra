"""The "shipped" mails: who wanted a roadmap item hears once that it is out
(``services.shipped``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hubra.core.models.platform_event import PlatformEvent
from hubra.core.models.support_case import RoadmapVote, SupportCase, SupportCaseVote
from hubra.core.models.user import User
from hubra.core.services import changelogs, platform_bot, shipped
from hubra.core.services.version import VersionService

PLAN = [
    {
        "id": "door-codes",
        "status": "done",
        "area": {},
        "title": {"de": "Türcodes", "en": "Door codes"},
        "summary": {"de": "Codes pro Raum.", "en": "Codes per room."},
        "version": "1.2.0",
        "link": None,
    },
    {
        "id": "older",
        "status": "done",
        "area": {},
        "title": {"en": "Older"},
        "summary": {},
        "version": "1.1.0",
        "link": None,
    },
    {
        "id": "planned",
        "status": "next",
        "area": {},
        "title": {"en": "Planned"},
        "summary": {},
        "version": "1.2.0",
        "link": None,
    },
]


def _user(db, address, **kw) -> User:
    user = User(email=address, first_name="A", last_name="B", **kw)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def _idea(db, reporter, item=None) -> SupportCase:
    case = SupportCase(
        kind="feature",
        status="open",
        title="Door codes please",
        description="…",
        user_id=reporter.id if reporter else None,
        roadmap_item=item,
        is_public=True,
    )
    db.session.add(case)
    db.session.commit()
    return case


@pytest.fixture
def plan():
    with patch.object(VersionService, "get_roadmap", return_value=PLAN):
        yield


@pytest.fixture
def people(app, db, plan):
    voter = _user(db, "voter@test.ch", language="en-GB")
    reporter = _user(db, "reporter@test.ch")
    idea_voter = _user(db, "idea-voter@test.ch")
    gone = _user(db, "gone@test.ch", is_disabled=True)
    other = _user(db, "other@test.ch")
    linked = _idea(db, reporter, "door-codes")
    unlinked = _idea(db, other)
    db.session.add_all(
        [
            RoadmapVote(item="door-codes", user_id=voter.id),
            RoadmapVote(item="door-codes", user_id=gone.id),
            RoadmapVote(item="older", user_id=other.id),
            SupportCaseVote(case_id=linked.id, user_id=idea_voter.id),
            SupportCaseVote(case_id=linked.id, user_id=voter.id),
            SupportCaseVote(case_id=unlinked.id, user_id=other.id),
        ]
    )
    db.session.commit()
    yield {"voter": voter, "reporter": reporter, "idea_voter": idea_voter}
    db.session.rollback()
    db.session.query(PlatformEvent).delete()
    db.session.commit()


def test_only_items_done_in_that_version_count(plan):
    assert [i["id"] for i in shipped.items_for("1.2.0")] == ["door-codes"]
    assert [i["id"] for i in shipped.items_for("v1.2.0")] == ["door-codes"]
    assert shipped.items_for("9.9.9") == []


def test_voters_and_linked_ideas_make_the_audience(people):
    ids = shipped.audience("door-codes")
    expected = {people["voter"].id, people["reporter"].id, people["idea_voter"].id}
    # Each person once; disabled accounts and other items' voters left out.
    assert set(ids) == expected and len(ids) == 3


def test_an_item_is_mailed_once(people):
    queued = []
    with patch(
        "hubra.core.tasks.after_commit.delay_after_commit",
        side_effect=lambda task, *args: queued.append(args),
    ):
        assert shipped.notify("1.2.0") == 1
        assert shipped.notify("1.2.0") == 0
    assert len(queued) == 1
    item, version, ids = queued[0]
    assert item == "door-codes" and version == "1.2.0" and len(ids) == 3
    mark = PlatformEvent.query.filter_by(kind=shipped.SENT).one()
    assert mark.message == "door-codes" and mark.details["people"] == 3


def test_nothing_runs_without_a_version(people):
    assert shipped.notify(None) == 0
    assert shipped.notify("") == 0


def test_each_mail_is_in_the_readers_language(people):
    calls = []
    with patch(
        "hubra.core.services.email.send_roadmap_shipped",
        side_effect=lambda to, name, **kw: calls.append((to, kw)) or True,
    ):
        sent = shipped.send_mails(
            "door-codes",
            "1.2.0",
            [people["voter"].id, people["reporter"].id],
        )
    assert sent == 2
    by_address = dict(calls)
    assert by_address["voter@test.ch"]["title"] == "Door codes"
    assert by_address["reporter@test.ch"]["title"] == "Türcodes"
    assert by_address["reporter@test.ch"]["version"] == "1.2.0"


def test_a_removed_item_sends_nothing(people):
    with patch("hubra.core.services.email.send_roadmap_shipped") as send:
        assert shipped.send_mails("gone-item", "1.2.0", [people["voter"].id]) == 0
    send.assert_not_called()


def test_the_changelog_tick_checks_the_running_version(app, db, monkeypatch):
    class Lock:
        def set(self, *a, **kw):
            return True

        def delete(self, *a):
            return None

        def get(self, *a):
            return None

    monkeypatch.setattr(platform_bot, "_redis", lambda: Lock())
    release = {"version": "1.2.0", "date": None, "sections": {}, "sections_de": {}}
    with (
        patch.object(changelogs, "hubra_release", return_value=release),
        patch.object(changelogs, "plugin_releases", return_value=[]),
        patch.object(changelogs, "_hubra_announced_before", return_value=True),
        patch.object(shipped, "notify") as notify,
    ):
        changelogs.announce()
    notify.assert_called_once_with("1.2.0")
    db.session.query(PlatformEvent).delete()
    db.session.commit()
    platform_bot._local.clear()


def test_the_mail_renders_in_both_languages(app, db):
    import hubra
    from hubra.core.models.translation import Translation
    from hubra.core.seeds import load_shipped_translations
    from hubra.core.services.mail_i18n import render_mail_template

    seeds = Path(hubra.__file__).parent / "core" / "seed_data" / "translations"
    for locale in ("de-CH", "en-GB"):
        texts = load_shipped_translations(seeds, locale)
        for key, value in texts.items():
            if "roadmap_shipped" in key:
                db.session.add(Translation(locale=locale, key=key, value=value))
    db.session.commit()

    with app.test_request_context():
        for locale, word in (("de-CH", "Jetzt da"), ("en-GB", "Out now")):
            html, text, subject = render_mail_template(
                "roadmap_shipped",
                locale=locale,
                name="Anna",
                club_name="Hubra",
                item_title="Door codes",
                item_summary="Codes per room.",
                version="1.2.0",
                roadmap_url="https://example.test/app/feedback/roadmap",
            )
            assert word in subject and "Door codes" in subject
            assert "1.2.0" in html and "1.2.0" in text
            assert "Codes per room." in html and "feedback/roadmap" in text


def test_the_mail_links_the_support_sites_roadmap_once_set(app, db):
    from hubra.core.models.platform_setting import PlatformSetting
    from hubra.core.services import email, platform_settings

    seen = {}

    def render(template, **kw):
        seen.update(kw)
        return "<p>x</p>", "x", "s"

    with (
        app.test_request_context(),
        patch.object(email, "render_mail_template", side_effect=render),
        patch.object(email, "_send", return_value=True),
    ):
        platform_settings.set_many({"support.url": "https://support.hubra.club/"})
        db.session.commit()
        assert email.send_roadmap_shipped(
            "a@test.ch", "A", title="T", summary="", version="1.2.0"
        )
    assert seen["roadmap_url"] == "https://support.hubra.club/roadmap"
    db.session.query(PlatformSetting).delete()
    db.session.commit()
