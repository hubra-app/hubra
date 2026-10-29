"""Tests for GET /api/v1/dashboard/summary."""

from datetime import date

from hubra.core.models.finance import Invoice, Transaction, TransactionCategory


def test_net_month_counts_money_that_moved(client, auth_headers, db, seeded_db):
    """Pending income (an unpaid invoice) is not this month's money yet; the
    finance overview agrees."""
    category = TransactionCategory(name="Beiträge", color="#123456")
    db.session.add(category)
    db.session.flush()
    today = date.today()

    def tx(amount, status, type_="income"):
        db.session.add(
            Transaction(
                date=today,
                description="t",
                category_id=category.id,
                amount=amount,
                method="IBAN",
                type=type_,
                status=status,
            )
        )

    tx(100, "Completed")
    tx(-30, "Completed", "expense")
    tx(500, "Pending")
    db.session.add(
        Invoice(
            member_id=seeded_db["admin"].id,
            issued=today,
            due=today,
            amount=500,
            status="Open",
        )
    )
    db.session.commit()

    stats = client.get("/api/v1/dashboard/summary", headers=auth_headers).get_json()["stats"]
    overview = client.get("/api/v1/finance/overview", headers=auth_headers).get_json()

    assert stats["netMonth"] == 70
    assert stats["netMonth"] == overview["netMTD"]
    assert stats["openInvoices"] == 1
    assert stats["openInvoicesAmount"] == 500
