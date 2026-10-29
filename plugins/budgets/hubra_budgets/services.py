"""Budget service: CRUD, line replacement, copy to a new year, and actuals."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import extract, func, select

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import Transaction, TransactionCategory

from .models import LINE_KINDS, Budget, BudgetLine

_ZERO = Decimal("0.00")


def _money(value) -> str:
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


def actuals(year: int) -> dict[tuple[int, str], Decimal]:
    """Completed transactions of ``year`` summed by (category, type)."""
    rows = db.session.execute(
        select(
            Transaction.category_id,
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(extract("year", Transaction.date) == year)
        .where(Transaction.status == "Completed")
        .group_by(Transaction.category_id, Transaction.type)
    ).all()
    return {(cat, kind): Decimal(total) for cat, kind, total in rows}


def budget_to_dict(budget: Budget, with_lines: bool = False) -> dict:
    booked = actuals(budget.year)
    totals = {k: {"planned": _ZERO, "actual": _ZERO} for k in LINE_KINDS}
    lines = []
    for line in budget.lines:
        actual = booked.get((line.category_id, line.kind), _ZERO)
        totals[line.kind]["planned"] += line.planned
        totals[line.kind]["actual"] += actual
        lines.append(
            {
                "id": line.id,
                "categoryId": line.category_id,
                "categoryName": line.category.name if line.category else None,
                "categoryColor": line.category.color if line.category else None,
                "kind": line.kind,
                "planned": _money(line.planned),
                "actual": _money(actual),
                "note": line.note,
            }
        )
    data = {
        "id": budget.id,
        "year": budget.year,
        "name": budget.name,
        "notes": budget.notes,
        "approved": budget.approved,
        "totals": {
            kind: {k: _money(v) for k, v in values.items()}
            for kind, values in totals.items()
        },
        "plannedResult": _money(
            totals["income"]["planned"] - totals["expense"]["planned"]
        ),
        "actualResult": _money(
            totals["income"]["actual"] - totals["expense"]["actual"]
        ),
    }
    if with_lines:
        data["lines"] = lines
        # Bookings in categories the budget has no line for, so nothing is
        # silently missing from the comparison.
        planned_keys = {(line.category_id, line.kind) for line in budget.lines}
        names = dict(
            db.session.execute(
                select(TransactionCategory.id, TransactionCategory.name)
            ).all()
        )
        data["unplanned"] = [
            {
                "categoryId": cat,
                "categoryName": names.get(cat),
                "kind": kind,
                "actual": _money(total),
            }
            for (cat, kind), total in sorted(booked.items())
            if (cat, kind) not in planned_keys and total
        ]
    return data


def _year(value) -> int:
    try:
        year = int(value)
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "year must be a number")
    if not 1900 <= year <= 2200:
        raise_error(400, "VALIDATION_ERROR", "year is out of range")
    return year


def _amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "planned must be an amount")
    # NaN passes quantize; Numeric(12, 2) holds less than 10^10.
    if not amount.is_finite() or amount >= Decimal("1e10"):
        raise_error(400, "VALIDATION_ERROR", "planned must be an amount")
    if amount < 0:
        raise_error(400, "VALIDATION_ERROR", "planned cannot be negative")
    return amount


class BudgetService:
    @staticmethod
    def list(year: int | None = None) -> list[Budget]:
        q = select(Budget).order_by(Budget.year.desc(), Budget.name)
        if year is not None:
            q = q.where(Budget.year == year)
        return list(db.session.scalars(q))

    @staticmethod
    def get(budget_id: int) -> Budget:
        budget = db.session.get(Budget, budget_id)
        if budget is None:
            raise_error(404, "NOT_FOUND", "Budget not found")
        return budget

    @staticmethod
    def _check_unique(year: int, name: str, exclude: int | None = None) -> None:
        q = select(Budget.id).where(Budget.year == year, Budget.name == name)
        if exclude is not None:
            q = q.where(Budget.id != exclude)
        if db.session.scalar(q) is not None:
            raise_error(409, "CONFLICT", f"A budget '{name}' for {year} exists")

    @staticmethod
    def create(data: dict, actor_id: int | None) -> Budget:
        name = (data.get("name") or "").strip()
        if not name:
            raise_error(400, "VALIDATION_ERROR", "name is required")
        year = _year(data.get("year"))
        BudgetService._check_unique(year, name)
        budget = Budget(year=year, name=name, notes=data.get("notes"))
        db.session.add(budget)
        db.session.flush()
        if data.get("lines") is not None:
            BudgetService.set_lines(budget.id, data["lines"], actor_id, audit=False)
        log_audit(actor_id, "create_budget", "Budget", budget.id, f"{name} {year}")
        return budget

    @staticmethod
    def update(budget_id: int, data: dict, actor_id: int | None) -> Budget:
        budget = BudgetService.get(budget_id)
        if budget.approved and data.get("approved") is not False:
            raise_error(409, "BUDGET_APPROVED", "Approved budgets cannot be changed")
        if "name" in data or "year" in data:
            name = (data.get("name", budget.name) or "").strip()
            if not name:
                raise_error(400, "VALIDATION_ERROR", "name cannot be empty")
            year = _year(data.get("year", budget.year))
            BudgetService._check_unique(year, name, exclude=budget.id)
            budget.name, budget.year = name, year
        if "notes" in data:
            budget.notes = data["notes"]
        if "approved" in data:
            budget.approved = bool(data["approved"])
        log_audit(actor_id, "update_budget", "Budget", budget.id, budget.name)
        db.session.flush()
        return budget

    @staticmethod
    def delete(budget_id: int, actor_id: int | None) -> None:
        budget = BudgetService.get(budget_id)
        if budget.approved:
            raise_error(409, "BUDGET_APPROVED", "Approved budgets cannot be deleted")
        log_audit(actor_id, "delete_budget", "Budget", budget.id, budget.name)
        db.session.delete(budget)
        db.session.flush()

    @staticmethod
    def set_lines(
        budget_id: int, lines: list, actor_id: int | None, audit: bool = True
    ) -> Budget:
        """Replace all lines. Each: {category_id, kind, planned, note?}."""
        budget = BudgetService.get(budget_id)
        if budget.approved:
            raise_error(409, "BUDGET_APPROVED", "Approved budgets cannot be changed")
        if not isinstance(lines, list):
            raise_error(400, "VALIDATION_ERROR", "lines must be a list")
        categories = set(db.session.scalars(select(TransactionCategory.id)))
        seen: set[tuple[int, str]] = set()
        new_lines = []
        for raw in lines:
            if not isinstance(raw, dict):
                raise_error(400, "VALIDATION_ERROR", "each line must be an object")
            kind = raw.get("kind")
            if kind not in LINE_KINDS:
                raise_error(
                    400, "VALIDATION_ERROR", f"kind must be one of {LINE_KINDS}"
                )
            cat = raw.get("category_id")
            if cat not in categories:
                raise_error(400, "VALIDATION_ERROR", f"unknown category {cat}")
            if (cat, kind) in seen:
                raise_error(400, "VALIDATION_ERROR", "a category appears twice")
            seen.add((cat, kind))
            new_lines.append(
                BudgetLine(
                    category_id=cat,
                    kind=kind,
                    planned=_amount(raw.get("planned")),
                    note=(raw.get("note") or None),
                )
            )
        budget.lines.clear()
        db.session.flush()
        budget.lines.extend(new_lines)
        if audit:
            log_audit(actor_id, "update_budget_lines", "Budget", budget.id, budget.name)
        db.session.flush()
        return budget

    @staticmethod
    def copy(budget_id: int, year, actor_id: int | None) -> Budget:
        """Start next year's budget from this one (lines and amounts)."""
        source = BudgetService.get(budget_id)
        target_year = _year(year if year is not None else source.year + 1)
        return BudgetService.create(
            {
                "name": source.name,
                "year": target_year,
                "notes": source.notes,
                "lines": [
                    {
                        "category_id": line.category_id,
                        "kind": line.kind,
                        "planned": line.planned,
                        "note": line.note,
                    }
                    for line in source.lines
                ],
            },
            actor_id,
        )
