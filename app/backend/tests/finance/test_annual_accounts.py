"""Annual accounts: the chart, the income statement and balance sheet built
from transactions, opening balances, the year close and its lock."""

from datetime import date
from decimal import Decimal

import pytest

from hubra.core.models.finance import Transaction, TransactionCategory

URL = "/api/v1/finance"


def _tx(db, day, amount, kind, category=None, method="IBAN", status="Completed"):
    tx = Transaction(
        date=day,
        description="x",
        amount=Decimal(amount) if kind == "income" else -Decimal(amount),
        type=kind,
        method=method,
        status=status,
        category_id=category.id if category else None,
    )
    db.session.add(tx)
    return tx


@pytest.fixture
def books(db, seeded_db):
    fees = TransactionCategory(name="Mitgliederbeiträge", color="#111111")
    rent = TransactionCategory(name="Miete Clubraum", color="#222222")
    misc = TransactionCategory(name="Diverses", color="#333333")
    db.session.add_all([fees, rent, misc])
    db.session.flush()
    _tx(db, date(2024, 12, 20), "500", "income", fees)  # before: opening bank
    _tx(db, date(2025, 2, 1), "3000", "income", fees)
    _tx(db, date(2025, 3, 1), "40", "income", fees, method="Cash")
    _tx(db, date(2025, 4, 1), "1200", "expense", rent)
    _tx(db, date(2025, 5, 1), "100", "expense", misc)
    _tx(db, date(2025, 6, 1), "999", "expense", rent, status="Pending")
    db.session.commit()
    return {"fees": fees, "rent": rent, "misc": misc}


def _line(rows, number):
    return next((r for r in rows if r["number"] == number), None)


def test_chart_is_seeded_and_categories_guessed(client, auth_headers, books):
    data = client.get(f"{URL}/accounts").get_json()
    numbers = {a["number"]: a for a in data["accounts"]}
    assert numbers["1020"]["isMoney"] and numbers["2800"]["kind"] == "equity"
    by_name = {c["name"]: c["accountId"] for c in data["categories"]}
    assert by_name["Mitgliederbeiträge"] == numbers["3000"]["id"]
    assert by_name["Miete Clubraum"] == numbers["6000"]["id"]
    assert by_name["Diverses"] is None


def test_income_statement_and_balance_sheet(client, auth_headers, books):
    r = client.get(f"{URL}/annual/2025").get_json()
    assert _line(r["income"], "3000")["amount"] == 3040
    assert _line(r["expense"], "6000")["amount"] == 1200  # pending not counted
    assert _line(r["expense"], "6900")["amount"] == 100  # no account: other
    assert r["result"] == 1740
    assert _line(r["assets"], "1020")["amount"] == 500 + 3000 - 1200 - 100
    assert _line(r["assets"], "1000")["amount"] == 40
    assert r["capital"]["opening"] == 500
    assert r["capital"]["closing"] == 2240
    assert r["totalAssets"] == 2240
    assert r["openingSource"] == "computed"
    assert r["notes"]["pendingBookings"] == 1
    # 2024 has a booking, so it is shown for comparison.
    assert r["hasPrevious"] is True


def test_opening_balances_by_hand(client, auth_headers, books):
    resp = client.put(
        f"{URL}/annual/2025/opening",
        json={"balances": {"1500": 800, "2400": 300}},
    )
    assert resp.status_code == 200
    r = resp.get_json()
    assert _line(r["assets"], "1500")["amount"] == 800
    assert _line(r["liabilities"], "2400")["amount"] == 300
    # Capital = assets - liabilities at the start: 500 bank + 800 - 300.
    assert r["capital"]["opening"] == 1000
    bad = client.put(f"{URL}/annual/2025/opening", json={"balances": {"3000": 1}})
    assert bad.status_code == 400


def test_close_locks_the_year_and_opens_the_next(client, auth_headers, books, db):
    # The year before has bookings and must be closed first.
    assert client.post(f"{URL}/annual/2025/close").status_code == 409
    assert client.post(f"{URL}/annual/2024/close").status_code == 200
    closed = client.post(f"{URL}/annual/2025/close").get_json()
    assert closed["closed"] is True

    nxt = client.get(f"{URL}/annual/2026").get_json()
    assert nxt["openingSource"] == "closing"
    assert _line(nxt["assets"], "1020")["amount"] == 2200
    assert nxt["capital"]["opening"] == 2240

    # No booking lands in, leaves or changes a closed year.
    resp = client.post(
        f"{URL}/transactions",
        json={
            "date": "2025-07-01",
            "description": "late",
            "amount": 10,
            "type": "income",
            "method": "IBAN",
        },
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "YEAR_CLOSED"
    db.session.rollback()

    # Reopening goes newest first.
    assert client.post(f"{URL}/annual/2024/reopen").status_code == 409
    assert client.post(f"{URL}/annual/2025/reopen").status_code == 200


def test_category_mapping_and_accounts(client, auth_headers, books):
    chart = client.get(f"{URL}/accounts").get_json()
    sponsoring = next(a for a in chart["accounts"] if a["number"] == "3200")
    misc = books["misc"]
    ok = client.put(
        f"{URL}/accounts/categories/{misc.id}", json={"accountId": sponsoring["id"]}
    )
    assert ok.status_code == 200
    bank = next(a for a in chart["accounts"] if a["number"] == "1020")
    bad = client.put(
        f"{URL}/accounts/categories/{misc.id}", json={"accountId": bank["id"]}
    )
    assert bad.status_code == 400
    new = client.post(
        f"{URL}/accounts", json={"number": "3700", "name": "Lager", "kind": "income"}
    )
    assert new.status_code == 201
    assert client.delete(f"{URL}/accounts/{bank['id']}").status_code == 409
    assert client.delete(f"{URL}/accounts/{new.get_json()['id']}").status_code == 204


def test_pdf(client, auth_headers, books):
    resp = client.get(f"{URL}/annual/2025.pdf")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"


def test_new_category_starts_on_a_guessed_account(client, auth_headers, books):
    client.get(f"{URL}/accounts")  # seeds the chart
    made = client.post(
        f"{URL}/transaction-categories",
        json={"name": "Verbandsbeitrag", "color": "#444444"},
    )
    assert made.status_code == 201
    chart = client.get(f"{URL}/accounts").get_json()
    federation = next(a for a in chart["accounts"] if a["number"] == "6700")
    mapped = next(c for c in chart["categories"] if c["name"] == "Verbandsbeitrag")
    assert mapped["accountId"] == federation["id"]
