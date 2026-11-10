"""One statement per member (roadmap idea 29).

Modules hand over what a member owes (a drinks tab, a booking fee, a shop
order) as open items through ``finance.open_item.add``; the treasurer can
add one by hand. With collecting on (finance setting ``collect_items``:
monthly or quarterly) a daily job puts each member's open items on one
invoice on the first day of the month or quarter, once they reach
``collect_min_amount``. With collecting off an item goes on an invoice of
its own straight away, as before.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice, OpenItem
from hubra.core.models.member import Member

CYCLES = ("off", "monthly", "quarterly")
# What fits in an invoice's description: the rest is on the PDF.
_DESCRIPTION_MAX = 512


def settings() -> dict:
    from hubra.core.modules import get_config

    config = get_config("finance")
    cycle = config.get("collect_items") or "off"
    try:
        minimum = Decimal(str(config.get("collect_min_amount") or 0))
    except ArithmeticError:
        minimum = Decimal(0)
    return {
        "cycle": cycle if cycle in CYCLES else "off",
        "min_amount": max(minimum, Decimal(0)),
    }


def is_billing_day(day: date, cycle: str) -> bool:
    """The first day of a month (monthly) or of a quarter (quarterly)."""
    if day.day != 1:
        return False
    return cycle == "monthly" or (cycle == "quarterly" and day.month in (1, 4, 7, 10))


def add(
    *,
    member_id: int,
    amount: Decimal,
    text: str,
    source: str,
    source_ref: str | None = None,
    category_id: int | None = None,
    day: date | None = None,
    actor_id: int | None = None,
) -> OpenItem:
    """Store an open item; with collecting off it is billed at once. A
    second item with the same ``source`` and ``source_ref`` is refused."""
    member = db.session.get(Member, member_id)
    if member is None or member.deleted_at is not None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
    if amount == 0:
        raise_error(400, "VALIDATION_ERROR", "amount: not zero")
    if source_ref is not None and db.session.scalar(
        select(OpenItem.id).where(
            OpenItem.source == source, OpenItem.source_ref == source_ref
        )
    ):
        raise_error(
            409, "ALREADY_ADDED", f"{source} {source_ref} is already an open item"
        )
    item = OpenItem(
        member_id=member_id,
        amount=amount,
        text=text.strip()[:200],
        day=day or date.today(),
        source=source,
        source_ref=source_ref,
        category_id=category_id,
    )
    db.session.add(item)
    db.session.flush()
    if settings()["cycle"] == "off" and amount > 0:
        _bill(member, [item], actor_id)
    return item


def remove(item: OpenItem) -> None:
    """Take an item back that is not billed yet (409 once it is)."""
    if item.invoice_id is not None:
        raise_error(409, "ALREADY_BILLED", "This item is already on an invoice")
    db.session.delete(item)
    db.session.flush()


def unbilled(member_id: int | None = None) -> list[OpenItem]:
    query = select(OpenItem).where(OpenItem.invoice_id.is_(None))
    if member_id is not None:
        query = query.where(OpenItem.member_id == member_id)
    return list(
        db.session.scalars(
            query.order_by(OpenItem.member_id, OpenItem.day, OpenItem.id)
        )
    )


def bill(
    *,
    member_id: int | None = None,
    force: bool = False,
    actor_id: int | None = None,
) -> list[Invoice]:
    """One invoice per member for their open items: those whose total
    reaches the minimum (any positive total with *force*). A member whose
    total is zero or less (credits) waits."""
    minimum = Decimal(0) if force else settings()["min_amount"]
    by_member: dict[int, list[OpenItem]] = defaultdict(list)
    for item in unbilled(member_id):
        by_member[item.member_id].append(item)
    invoices = []
    for mid, items in by_member.items():
        total = sum((i.amount for i in items), Decimal(0))
        if total <= 0 or total < minimum:
            continue
        member = db.session.get(Member, mid)
        if member is None or member.archived_at is not None:
            continue
        invoices.append(_bill(member, items, actor_id))
    return invoices


def _bill(member: Member, items: list[OpenItem], actor_id: int | None) -> Invoice:
    from hubra.api.finance.services import InvoicesService, default_due_date

    total = sum((i.amount for i in items), Decimal(0))
    categories = {i.category_id for i in items}
    if len(items) == 1:
        description = items[0].text
    else:
        lines = "; ".join(f"{i.text} {i.amount:.2f}" for i in items)
        description = f"{len(items)}: {lines}"
    if len(description) > _DESCRIPTION_MAX:
        description = description[: _DESCRIPTION_MAX - 1] + "…"
    today = date.today()
    invoice = InvoicesService.create(
        {
            "member_id": member.id,
            "issued": today,
            "due": default_due_date(today),
            "amount": total,
            "purpose": "other",
            "description": description,
            # One category when they share it; else the books pick one.
            "category_id": categories.pop() if len(categories) == 1 else None,
        },
        actor_id,  # type: ignore[arg-type]
    )
    for item in items:
        item.invoice_id = invoice.id
    db.session.flush()
    return invoice


def items_of(invoice_id: int) -> list[OpenItem]:
    """The open items an invoice bills, for its detail page and its PDF."""
    return list(
        db.session.scalars(
            select(OpenItem)
            .where(OpenItem.invoice_id == invoice_id)
            .order_by(OpenItem.day, OpenItem.id)
        )
    )


def dump(item: OpenItem) -> dict:
    member = item.member
    return {
        "id": item.id,
        "member_id": item.member_id,
        "member_name": member.name if member is not None else None,
        "amount": float(item.amount),
        "text": item.text,
        "day": item.day.isoformat(),
        "source": item.source,
        "source_ref": item.source_ref,
        "category_id": item.category_id,
        "invoice_id": item.invoice_id,
    }
