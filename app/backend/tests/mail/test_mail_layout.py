"""The branded mail layout: logo in the header, sent as an inline image."""

import base64

from flask import g

from hubra.core.models.tenant import Tenant
from hubra.core.models.translation import Translation
from hubra.core.services.email import _mail_body
from hubra.core.services.mail_i18n import mail_logo_src, render_mail_template

_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nclub-logo").decode()


def _club(logo: str | None) -> Tenant:
    return Tenant(
        name="Alpha Club", slug="alpha", settings={"branding": {"logo": logo}}
    )


def test_without_a_club_logo_the_header_shows_the_hubra_mark(app, db):
    src = mail_logo_src()
    assert src.startswith("data:image/png;base64,")
    assert base64.b64decode(src.split(",", 1)[1]).startswith(b"\x89PNG")


def test_a_club_logo_replaces_the_mark(app, db):
    g.tenant = _club(f"data:image/png;base64,{_PNG}")
    try:
        assert mail_logo_src() == f"data:image/png;base64,{_PNG}"
    finally:
        g.tenant = None


def test_an_svg_or_huge_club_logo_falls_back_to_the_mark(app, db):
    big = base64.b64encode(b"x" * 300_000).decode()
    for logo in ("data:image/svg+xml;base64,PHN2Zy8+", f"data:image/png;base64,{big}"):
        g.tenant = _club(logo)
        try:
            assert mail_logo_src() != logo
        finally:
            g.tenant = None


def test_the_logo_travels_as_an_inline_image(app, db):
    for key, value in {
        "mail.email.greeting": "Hi {{name}},",
        "mail.email.password_reset.body": "Reset your password.",
        "mail.email.password_reset.cta_note": "Use the button",
        "mail.email.password_reset.button": "Reset password",
        "mail.email.password_reset.ignore": "Ignore it.",
        "mail.email.button_fallback": "Or open:",
        "mail.email.footer": "Sent by {{club_name}}.",
        "mail.email.sent_with": "Sent with",
        "mail.email.subject.password_reset": "Reset",
    }.items():
        db.session.add(Translation(locale="en-GB", key=key, value=value))
    db.session.commit()

    with app.test_request_context():
        html, text, _ = render_mail_template(
            "password_reset",
            "en-GB",
            name="Anna",
            club_name="Alpha Club",
            reset_url="https://sso.example/reset#token=x",
        )
    assert 'href="https://sso.example/reset#token=x"' in html
    assert ">Reset password</a>" in html

    body = _mail_body(html, text)
    assert body.get_content_type() == "multipart/related"
    alt, image = body.get_payload()
    sent_html = alt.get_payload()[1].get_payload(decode=True).decode()
    assert "data:image" not in sent_html
    cid = image["Content-ID"].strip("<>")
    assert f'src="cid:{cid}"' in sent_html
    assert image.get_content_type() == "image/png"


def test_a_mail_without_images_stays_plain_alternative(app):
    body = _mail_body("<p>Hi</p>", "Hi")
    assert body.get_content_type() == "multipart/alternative"


def _password_reset_texts(db) -> None:
    for key, value in {
        "mail.email.greeting": "Hi {{name}},",
        "mail.email.password_reset.body": "Reset your password.",
        "mail.email.password_reset.cta_note": "Use the button",
        "mail.email.password_reset.button": "Reset password",
        "mail.email.password_reset.ignore": "Ignore it.",
        "mail.email.button_fallback": "Or open:",
        "mail.email.footer": "Sent by {{club_name}}.",
        "mail.email.sent_with": "Sent with",
        "mail.email.subject.password_reset": "Reset",
    }.items():
        db.session.add(Translation(locale="en-GB", key=key, value=value))
    db.session.commit()


def _render_reset(app) -> str:
    with app.test_request_context():
        html, _, _ = render_mail_template(
            "password_reset",
            "en-GB",
            name="Anna",
            club_name="Alpha Club",
            reset_url="https://sso.example/reset#token=x",
        )
    return html


def _footer_texts(db) -> None:
    db.session.add(
        Translation(
            locale="en-GB",
            key="mail.email.footer_report",
            value="Not meant for you? Tell us.",
        )
    )
    db.session.add(
        Translation(locale="en-GB", key="mail.email.footer_unsubscribe", value="Unsubscribe")
    )


def test_every_mail_footer_links_report_and_unsubscribe(app, db):
    from hubra.core.services import platform_settings

    _password_reset_texts(db)
    _footer_texts(db)
    platform_settings.set_many({"support.url": "https://support.hubra.club/"})
    db.session.commit()
    with app.test_request_context():
        html, text, _ = render_mail_template(
            "password_reset",
            "en-GB",
            name="Anna",
            club_name="Alpha Club",
            reset_url="https://sso.example/reset#token=x",
        )
    assert 'href="https://support.hubra.club/melden?mail=password_reset"' in html
    assert ">Not meant for you? Tell us.</a>" in html
    assert 'href="https://support.hubra.club/konto#mails"' in html
    # The plain-text part carries the same links.
    assert "Not meant for you? Tell us. https://support.hubra.club/melden?mail=password_reset" in text
    assert "Unsubscribe: https://support.hubra.club/konto#mails" in text


def test_no_footer_links_without_a_support_site_or_its_text(app, db):
    from hubra.core.services import platform_settings

    _password_reset_texts(db)
    platform_settings.set_many({"support.url": ""})
    db.session.commit()
    assert "/melden" not in _render_reset(app)
    # Set, but `flask seed` has not loaded the texts yet: no "[key]" in mails.
    platform_settings.set_many({"support.url": "https://support.hubra.club"})
    db.session.commit()
    html = _render_reset(app)
    assert "/melden" not in html
    assert "[mail.email.footer_report]" not in html
