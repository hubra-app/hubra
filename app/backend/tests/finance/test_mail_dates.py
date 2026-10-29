"""Due dates in invoice mails are written the way the reader writes them."""

from datetime import date
from unittest.mock import patch

from hubra.core.services.mail_format import mail_date
from hubra.core.tasks.finance_tasks import _render_invoice_reminder


def test_mail_date_by_language():
    due = date(2026, 11, 5)
    assert mail_date(due, "de-CH") == "05.11.2026"
    assert mail_date(due, "fr-CH") == "05.11.2026"
    assert mail_date(due, "en-GB") == "05/11/2026"
    assert mail_date(due, None) == "05.11.2026"


def test_reminder_mail_gets_a_swiss_date(app, db):
    with (
        app.app_context(),
        patch(
            "hubra.core.tasks.finance_tasks.render_mail_template",
            return_value=("", "", ""),
        ) as render,
    ):
        _render_invoice_reminder("Anna", 7, 45.0, date(2026, 11, 5), "", lang="de-CH")
    assert render.call_args.kwargs["due_date"] == "05.11.2026"
