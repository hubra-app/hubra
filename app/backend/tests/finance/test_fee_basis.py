"""The yearly expenses behind percentage and formula tiers: where the sum
comes from, its lines per category, and what the tiers cost with it."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from hubra.api.finance import fee_basis as fb
from hubra.api.finance.fee_basis import fee_basis
from hubra.core.models.finance import (
    RecurringTransaction,
    Transaction,
    TransactionCategory,
)
from hubra.core.models.setting import Setting

URL = "/api/v1/finance/fee-basis"


def _config(**values):
    return patch("hubra.core.modules.get_config", return_value=values)


@pytest.fixture
def books(db):
    rent = TransactionCategory(name="Miete", color="#e8590c")
    power = TransactionCategory(name="Strom", color="#1c7ed6")
    db.session.add_all([rent, power])
    db.session.flush()
    rules = [
        ("Miete", "monthly", "1000", rent, True, True),
        ("Strom", "quarterly", "150", power, True, True),
        ("Spende", "yearly", "500", None, False, True),  # does not count
        ("Alte Miete", "monthly", "800", rent, True, False),  # stopped
    ]
    for text, interval, amount, category, counts, active in rules:
        db.session.add(
            RecurringTransaction(
                description=text,
                type="expense",
                amount=Decimal(amount),
                category_id=category.id if category else None,
                method="IBAN",
                interval=interval,
                start_date=date(2026, 1, 1),
                next_date=date(2026, 11, 1),
                book_completed=False,
                counts_for_fees=counts,
                active=active,
            )
        )
    for day, amount, category, status in [
        (date(2025, 3, 1), -6000, rent, "Completed"),
        (date(2025, 6, 1), -400, power, "Completed"),
        (date(2025, 7, 1), -99, power, "Pending"),  # not confirmed
        (date(2025, 8, 1), 3000, None, "Completed"),  # income
        (date(2026, 2, 1), -1000, rent, "Completed"),  # this year
    ]:
        db.session.add(
            Transaction(
                date=day,
                description="x",
                category_id=category.id if category else None,
                amount=Decimal(amount),
                method="IBAN",
                type="income" if amount > 0 else "expense",
                status=status,
            )
        )
    db.session.add(Setting(key=fb.LEGACY_SETTING, value="7000"))
    db.session.commit()


def test_manual_keeps_the_old_setting(app, db, books):
    with _config():
        basis = fee_basis(today=date(2026, 10, 31))
    assert basis["source"] == "manual"
    assert basis["total"] == 7000
    assert basis["lines"] == []
    with _config(fee_basis_manual=8000, fee_basis_extra=500):
        assert fee_basis()["total"] == 8000  # extra is for the other sources


def test_budget_needs_the_plugin(app, db, books, monkeypatch):
    monkeypatch.setattr(fb, "_PLUGIN_SOURCES", {})
    with _config(fee_basis_source="budget", fee_basis_extra=100):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "budget" not in basis["sources"]
    assert basis["note"] == "NO_BUDGET"
    assert basis["total"] == 100


def test_budget_from_a_registered_plugin(app, db, books, monkeypatch):
    monkeypatch.setattr(fb, "_PLUGIN_SOURCES", {})
    lines = [{"category_id": None, "name": "Anlässe", "amount": 2500, "items": []}]
    fb.register_source("budget", "finance.budgets", lambda year: lines)
    with (
        _config(fee_basis_source="budget"),
        patch("hubra.core.modules.is_enabled", return_value=True),
    ):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "budget" in basis["sources"]
    assert basis["period"] == {"year": 2026}
    assert basis["total"] == 2500


def test_a_registered_source_with_its_own_period(app, db, books, monkeypatch):
    monkeypatch.setattr(fb, "_BASIS_SOURCES", dict(fb._BASIS_SOURCES))
    lines = [{"category_id": None, "name": "Halle", "amount": 1200, "items": []}]
    fb.register_basis_source(
        "ledger", "finance.books", lambda today: (lines, {"year": today.year})
    )

    def enabled(code, **_):
        return code == "finance.books"

    with (
        _config(fee_basis_source="ledger"),
        patch("hubra.core.modules.is_enabled", side_effect=enabled),
    ):
        basis = fee_basis(today=date(2026, 10, 31))
    assert basis["sources"][0] == "manual"
    assert "ledger" in basis["sources"]
    assert basis["period"] == {"year": 2026}
    assert basis["total"] == 1200

    # With the module that provides it switched off, the sum is only the extra.
    with (
        _config(fee_basis_source="ledger", fee_basis_extra=50),
        patch("hubra.core.modules.is_enabled", return_value=False),
    ):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "ledger" not in basis["sources"]
    assert basis["note"] == "NO_LEDGER"
    assert basis["total"] == 50


# ── Sources offered as contracts (docs/contracts.md) ────────────────────────


def hall_source(ctx, data):
    return {
        "lines": [{"category_id": None, "name": "Halle", "amount": 1500}],
        "period": {"year": data.on.year},
    }


def broken_source(ctx, data):
    raise RuntimeError("boom")


@pytest.fixture
def contract_source(app, db, monkeypatch):
    from hubra.api.finance.contracts import FeeBasisIn, FeeBasisOut
    from hubra.core.contracts import query_contract
    from hubra.core.modules import Module, registry

    def offer(handler):
        module = Module(
            code="demo.hall",
            name="Hall",
            provides=(
                query_contract(
                    "demo.hall.fee_basis.hall",
                    f"{__name__}:{handler}",
                    input=FeeBasisIn,
                    output=FeeBasisOut,
                ),
            ),
        )
        monkeypatch.setitem(registry._modules, "demo.hall", module)

    monkeypatch.setattr(
        "hubra.core.modules.state.is_enabled", lambda code, tenant_id=None: True
    )
    return offer


def test_a_source_offered_as_a_query(app, db, books, contract_source):
    contract_source("hall_source")
    with _config(fee_basis_source="hall", fee_basis_extra=100):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "hall" in basis["sources"]
    assert basis["source"] == "hall"
    assert basis["period"] == {"year": 2026}
    assert basis["total"] == 1600
    assert basis["lines"][0]["name"] == "Halle"


def test_a_query_source_whose_module_is_off(
    app, db, books, contract_source, monkeypatch
):
    contract_source("hall_source")
    monkeypatch.setattr(
        "hubra.core.modules.state.is_enabled", lambda code, tenant_id=None: False
    )
    with _config(fee_basis_source="hall", fee_basis_extra=50):
        basis = fee_basis(today=date(2026, 10, 31))
    assert "hall" not in basis["sources"]
    assert basis["note"] == "NO_HALL"
    assert basis["total"] == 50


def test_a_broken_query_source_falls_back_to_the_old_setting(
    app, db, books, contract_source
):
    contract_source("broken_source")
    with _config(fee_basis_source="hall"):
        assert fb.yearly_expenses() == Decimal("7000")
