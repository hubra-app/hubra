"""GET /finance/summary: income and expenses per category over a date range."""

from datetime import date
from decimal import Decimal

from hubra.core.models.finance import Transaction, TransactionCategory


def _tx(db, day, amount, category=None, status="Completed"):
    db.session.add(
        Transaction(
            date=day,
            description="x",
            category_id=category.id if category else None,
            amount=Decimal(str(amount)),
            method="Cash",
            type="income" if amount > 0 else "expense",
            status=status,
        )
    )


def _seed(db):
    rent = TransactionCategory(name="Rent", color="#111111")
    fees = TransactionCategory(name="Fees", color="#222222")
    db.session.add_all([rent, fees])
    db.session.flush()
    _tx(db, date(2026, 1, 5), -1200, rent)
    _tx(db, date(2026, 6, 5), -1200, rent)
    _tx(db, date(2026, 3, 1), 500, fees)
    _tx(db, date(2026, 3, 2), 250, fees)
    _tx(db, date(2026, 4, 1), -30)  # no category
    _tx(db, date(2026, 5, 1), 999, fees, status="Pending")  # not booked yet
    _tx(db, date(2025, 12, 31), -5000, rent)  # last year
    db.session.commit()
    return rent, fees


def test_sums_per_category_for_a_year(client, auth_headers, db):
    rent, fees = _seed(db)
    resp = client.get(
        "/api/v1/finance/summary?from=2026-01-01&to=2026-12-31", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["income"] == 750
    assert body["expense"] == 2430
    assert body["net"] == -1680
    by_id = {c["id"]: c for c in body["categories"]}
    assert by_id[rent.id] == {
        "id": rent.id,
        "name": "Rent",
        "color": "#111111",
        "income": 0,
        "expense": 2400,
        "net": -2400,
        "count": 2,
    }
    assert by_id[fees.id]["income"] == 750
    assert by_id[fees.id]["count"] == 2
    assert by_id[None]["expense"] == 30
    assert by_id[None]["name"] is None
    # Largest first
    assert [c["id"] for c in body["categories"]] == [rent.id, fees.id, None]


def test_to_defaults_to_end_of_the_from_year(client, auth_headers, db):
    _seed(db)
    body = client.get(
        "/api/v1/finance/summary?from=2025-01-01", headers=auth_headers
    ).get_json()
    assert body["to"] == "2025-12-31"
    assert body["expense"] == 5000


def test_bad_range_is_refused(client, auth_headers, db):
    for query in ("from=nope", "from=2026-05-01&to=2026-01-01", "from=2000-01-01&to=2026-01-01"):
        resp = client.get(f"/api/v1/finance/summary?{query}", headers=auth_headers)
        assert resp.status_code == 400, query
