"""The monthly account statement mailed to the club's finance address."""

import base64
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from hubra.api.finance.statement import chf, month_of, statement_data
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory

ON = {"statement_enabled": True, "statement_email": "kasse@verein.ch"}
SEEDS = Path(__file__).resolve().parents[2] / "hubra/core/seed_data/translations"


@pytest.fixture
def mail_texts(db):
    """The shipped German texts of the statement mail."""
    from hubra.core.models.translation import Translation

    texts = json.loads((SEEDS / "de-CH.json").read_text(encoding="utf-8"))
    for key, value in texts.items():
        if "account_statement" in key:
            db.session.add(Translation(locale="de-CH", key=key, value=value))
    db.session.commit()


def _tx(db, day, amount, category=None, status="Completed", text="x"):
    db.session.add(
        Transaction(
            date=day,
            description=text,
            category_id=category.id if category else None,
            amount=Decimal(str(amount)),
            method="IBAN",
            type="income" if amount > 0 else "expense",
            status=status,
        )
    )


@pytest.fixture
def books(db):
    rent = TransactionCategory(name="Miete", color="#e8590c")
    fees = TransactionCategory(name="Beiträge", color="#7441e0")
    db.session.add_all([rent, fees])
    db.session.flush()
    _tx(db, date(2026, 9, 30), 1000, fees)  # before the month
    _tx(db, date(2026, 10, 1), -850, rent, text="Miete Oktober")
    _tx(db, date(2026, 10, 15), 120, fees, text="Beitrag Anna")
    _tx(db, date(2026, 10, 20), 120, fees, text="Beitrag Ben")
    _tx(db, date(2026, 10, 25), -40, status="Pending")
    _tx(db, date(2026, 11, 2), 500, fees)  # after the month
    db.session.add(
        Invoice(
            issued=date(2026, 10, 1),
            due=date(2026, 10, 20),
            amount=Decimal("120"),
            status="Open",
            purpose="other",
        )
    )
    db.session.commit()


def test_statement_data(app, db, books):
    data = statement_data(date(2026, 10, 1))
    assert data["end"] == date(2026, 10, 31)
    assert data["opening"] == 1000
    assert data["income"] == 240
    assert data["expense"] == 850
    assert data["closing"] == 390
    assert [t["description"] for t in data["transactions"]] == [
        "Miete Oktober",
        "Beitrag Anna",
        "Beitrag Ben",
    ]
    assert data["transactions"][0]["category"] == "Miete"
    assert data["pending"] == {"count": 1, "amount": -40}
    assert data["open_invoices"] == {"count": 1, "amount": 120, "overdue": 1}
    assert {c["name"] for c in data["categories"]} == {"Miete", "Beiträge"}


def test_month_of():
    assert month_of("2026-02") == date(2026, 2, 1)
    last = month_of(None)
    assert last.day == 1 and last < date.today().replace(day=1)


def test_chf():
    assert chf(1234.5) == "1’234.50"
    assert chf(-40) == "−40.00"


def test_pdf_download(client, auth_headers, db, books):
    resp = client.get(
        "/api/v1/finance/statement.pdf?month=2026-10", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")
    assert "kontoauszug-2026-10.pdf" in resp.headers["Content-Disposition"]


def test_monthly_task_mails_last_month(app, db, books, mail_texts):
    from hubra.core.tasks.finance_tasks import _send_account_statements

    with (
        patch("hubra.core.modules.get_config", return_value=ON),
        patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay,
    ):
        assert _send_account_statements(today=date(2026, 11, 1)) == {"sent": 1}

    delay.assert_called_once()
    mail = delay.call_args.kwargs
    assert mail["to_email"] == "kasse@verein.ch"
    assert "Oktober 2026" in mail["subject"]
    assert "Saldo am Monatsende" in mail["body_text"]
    assert "390.00" in mail["body_text"]
    (attachment,) = mail["attachments"]
    assert attachment["name"] == "kontoauszug-2026-10.pdf"
    assert base64.b64decode(attachment["content"]).startswith(b"%PDF")


@pytest.mark.parametrize(
    "config",
    [{}, {"statement_enabled": True}, {"statement_email": "kasse@verein.ch"}],
)
def test_no_statement_unless_switched_on_with_an_address(app, db, config):
    from hubra.core.tasks.finance_tasks import _send_account_statements

    with (
        patch("hubra.core.modules.get_config", return_value=config),
        patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay,
    ):
        assert _send_account_statements(today=date(2026, 11, 1)) == {"sent": 0}
    delay.assert_not_called()


def test_send_now(client, auth_headers, db, books):
    url = "/api/v1/finance/statement/send"
    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay:
        with patch("hubra.core.modules.get_config", return_value={}):
            resp = client.post(url, json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "STATEMENT_EMAIL_MISSING"

        with patch("hubra.core.modules.get_config", return_value=ON):
            resp = client.post(url, json={"month": "2026-10"}, headers=auth_headers)
        assert resp.status_code == 202
        assert resp.get_json() == {"month": "2026-10", "to": "kasse@verein.ch"}
    delay.assert_called_once()
