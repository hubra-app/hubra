"""Invoice mails link to the member's personal start page in their club.

They used to point at ``<frontend>/invoices``, which the app does not serve
(club pages live below ``/<club>/app``), so the button opened a 404.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from hubra.core.models.finance import Invoice
from tests.finance.test_overdue_reminders import run  # noqa: F401

BASE = "https://app.hubra.club"


@pytest.fixture
def frontend(app, monkeypatch):
    monkeypatch.setitem(app.config, "FRONTEND_BASE_URL", BASE + "/")


def _my_invoices_url():
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    prefix = f"/{tenant.slug}" if tenant else ""
    return f"{BASE}{prefix}/app/dashboard/me"


def test_club_app_url_names_the_club(app, db, frontend):
    from hubra.core.services.email import club_app_url

    assert club_app_url("/app/dashboard/me") == _my_invoices_url()


def test_club_app_url_puts_the_club_slug_first(app, db, frontend):
    from types import SimpleNamespace

    from flask import g

    from hubra.core.services.email import club_app_url

    previous = getattr(g, "tenant", None)
    g.tenant = SimpleNamespace(slug="fc-demo")
    try:
        assert club_app_url("/app/dashboard/me") == f"{BASE}/fc-demo/app/dashboard/me"
    finally:
        g.tenant = previous


def test_club_app_url_is_empty_without_a_frontend(app, db, monkeypatch):
    from hubra.core.services.email import club_app_url

    monkeypatch.setitem(app.config, "FRONTEND_BASE_URL", "")
    assert club_app_url("/app/dashboard/me") == ""


def test_overdue_reminder_links_to_the_personal_start_page(
    db, seeded_db, frontend, run  # noqa: F811
):
    admin = seeded_db["admin"]
    admin.private_email_verified = True
    db.session.add(
        Invoice(
            member_id=admin.id,
            issued=date.today() - timedelta(days=40),
            due=date.today() - timedelta(days=8),
            amount=Decimal("50.00"),
            status="Open",
        )
    )
    db.session.commit()

    result, mail, _ = run()

    assert result["overdue_7d"] == 1
    # The button in the HTML mail.
    body = mail.call_args.kwargs["body_html"]
    assert f'href="{_my_invoices_url()}"' in body
    assert f"{BASE}/invoices" not in body
