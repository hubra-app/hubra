"""Mail and invoices name the club, not a placeholder."""

from flask import g

from hubra.core.models.setting import Setting
from hubra.core.models.tenant import Tenant
from hubra.core.services.email import club_display_name


def test_a_club_without_the_setting_uses_its_platform_name(app, db):
    g.tenant = Tenant(name="Alpha Club", slug="alpha")
    try:
        assert club_display_name() == "Alpha Club"
    finally:
        g.tenant = None


def test_the_club_name_setting_still_wins(app, db):
    db.session.merge(Setting(key="club.name", value="Alpha e.V."))
    db.session.commit()
    g.tenant = Tenant(name="Alpha Club", slug="alpha")
    try:
        assert club_display_name() == "Alpha e.V."
    finally:
        g.tenant = None


def test_without_a_club_it_is_the_platform(app, db):
    assert club_display_name() == "Hubra"


def test_the_plain_text_part_has_no_html_tags(app, db):
    from hubra.core.models.translation import Translation
    from hubra.core.services.mail_i18n import render_mail_template

    for key, value in {
        "mail.email.club_invite.intro": (
            "{{invited_by}} invited you to join <strong>{{club_name}}</strong>."
        ),
        "mail.email.club_invite.cta_text": "Open the link &amp; accept:",
        "mail.email.club_invite.ignore": "Ignore it.",
        "mail.email.subject.club_invite": "[{{club_name}}] You're invited",
    }.items():
        db.session.add(Translation(locale="en-GB", key=key, value=value))
    db.session.commit()

    with app.test_request_context():
        html, text, subject = render_mail_template(
            "club_invite",
            "en-GB",
            club_name="Alpha Club",
            invited_by="Alice",
            invite_url="https://sso.example/invite#token=x",
        )
    assert "<strong>Alpha Club</strong>" in html
    assert "Alice invited you to join Alpha Club." in text
    assert "Open the link & accept:" in text
    assert "<" not in text
    assert subject == "[Alpha Club] You're invited"


def test_a_new_club_mails_in_the_platform_texts(app, db):
    """A club schema starts with an empty translation table (Postgres)."""
    from collections import namedtuple
    from unittest.mock import patch

    from hubra.core.models.translation import Translation
    from hubra.core.services.mail_i18n import get_mail_translator

    Row = namedtuple("Row", "key value alias_for")
    db.session.add(Translation(locale="de-CH", key="mail.a", value=""))  # reported
    db.session.add(Translation(locale="de-CH", key="mail.b", value="Eigen"))
    db.session.commit()
    platform = {
        "de-CH": [
            Row("mail.a", "Plattform A", None),
            Row("mail.b", "Plattform B", None),
        ],
        "en-GB": [Row("mail.c", "Platform C", None)],
    }
    with patch(
        "hubra.api.i18n.services.platform_rows", side_effect=lambda loc: platform[loc]
    ):
        t = get_mail_translator("de-CH")
    assert (t("mail.a"), t("mail.b"), t("mail.c")) == (
        "Plattform A",
        "Eigen",
        "Platform C",
    )


def test_names_with_special_characters_stay_one_address(app, db):
    from email import message_from_string, policy
    from unittest.mock import patch

    from hubra.core.services import email

    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            pass

        def sendmail(self, sender, rcpts, raw):
            sent["raw"] = raw

    route = email._Route("relay", 25, None, None)
    with patch.object(email.smtplib, "SMTP", FakeSMTP):
        email._send_via_smtp(
            "dora@example.com",
            "Dora <img src=x>, Müller",
            "noreply@example.com",
            "Verein Grün & Co.",
            "Hallo",
            "<p>x</p>",
            "x",
            route=route,
        )
    msg = message_from_string(sent["raw"], policy=policy.default)
    to = [(a.display_name, a.addr_spec) for a in msg["To"].addresses]
    sender = [(a.display_name, a.addr_spec) for a in msg["From"].addresses]
    assert to == [("Dora <img src=x>, Müller", "dora@example.com")]
    assert sender == [("Verein Grün & Co.", "noreply@example.com")]


def test_the_subject_shows_the_club_name_as_typed(app, db):
    from hubra.core.models.translation import Translation
    from hubra.core.services.mail_i18n import render_mail_template

    db.session.add(
        Translation(
            locale="en-GB",
            key="mail.email.subject.club_invite",
            value="[{{club_name}}] You're invited",
        )
    )
    db.session.commit()
    with app.test_request_context():
        _, _, subject = render_mail_template(
            "club_invite",
            "en-GB",
            club_name="Müller & Söhne",
            invited_by="Alice",
            invite_url="https://sso.example/invite#token=x",
        )
    assert subject == "[Müller & Söhne] You're invited"
