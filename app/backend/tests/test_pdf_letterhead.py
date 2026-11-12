"""One letterhead for every PDF (hubra/core/services/pdf.py)."""

from __future__ import annotations

import base64
from unittest.mock import patch

from hubra.core.contracts import SYSTEM, call
from hubra.core.models.setting import Setting
from hubra.core.models.tenant import Tenant
from hubra.core.services import pdf

LOGO = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()


def _club(db, **branding) -> Tenant:
    tenant = Tenant(
        name="FC Demo", slug="fc-demo", status="active", settings={"branding": branding}
    )
    db.session.add(tenant)
    for key, value in (
        ("Club.Banking.Street", "Seestrasse"),
        ("Club.Banking.HouseNo", "12"),
        ("Club.Banking.PostalCode", "8000"),
        ("Club.Banking.City", "Zürich"),
        ("Club.Contact.FinanceEmail", "kasse@fc-demo.ch"),
    ):
        db.session.merge(Setting(key=key, value=value))
    db.session.commit()
    return tenant


def test_the_letterhead_comes_from_the_club(app, db, seeded_db):
    tenant = _club(db, logo=LOGO, primary_color="#7c3aed", website="https://fc-demo.ch")
    with (
        app.test_request_context(),
        patch("hubra.core.services.pdf._tenant", return_value=tenant),
        patch("hubra.core.services.email.club_display_name", return_value="FC Demo"),
    ):
        head = pdf.letterhead()
        html = pdf.html("<p>Hallo &amp; willkommen</p>", title="Brief", head=head)
    assert head["address"] == ["Seestrasse 12", "8000 Zürich"]
    assert head["color"] == "#7c3aed" and head["logo"] == LOGO
    assert "FC Demo" in html and "kasse@fc-demo.ch" in html
    assert "border-bottom: 2px solid #7c3aed" in html
    assert "counter(pages)" in html


def test_a_bad_colour_or_logo_is_left_out(app, db, seeded_db):
    tenant = _club(db, logo="javascript:alert(1)", primary_color="red;}body{x")
    with (
        app.test_request_context(),
        patch("hubra.core.services.pdf._tenant", return_value=tenant),
    ):
        head = pdf.letterhead()
    assert head["logo"] is None
    assert head["color"] == pdf.DEFAULT_COLOR


def test_plugins_render_through_the_action(app, db, seeded_db):
    with app.test_request_context():
        out = call(
            "pdf.render",
            title="Protokoll",
            body_html="<h1>Protokoll</h1><p>Text</p>",
            actor=SYSTEM,
        )
    assert base64.b64decode(out["pdf_base64"]).startswith(b"%PDF")
