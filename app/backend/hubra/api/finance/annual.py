"""Annual accounts (Jahresrechnung): a chart of accounts, fiscal years with
opening and closing balances, the income statement (Erfolgsrechnung) and the
balance sheet (Bilanz), and the year close.

Hubra books money in and out, not double entry, so the accounts are derived:

* Income statement: every completed transaction of the year counts on the
  account of its category, or on "other income" / "other expenses" when the
  category has none. This is the cash view, as most Swiss clubs keep it.
* Balance sheet: the money accounts (cash for transactions paid in cash, the
  bank for everything else) move with the transactions; other asset and
  liability accounts keep their opening balance; the club's capital
  (Vereinsvermögen) is assets minus liabilities at the start, plus the
  year's result. So both sides always match.

A year's opening balances are the closing balances of the closed year
before it. Without one, the money accounts open with everything booked
before the year, and the board can set the other accounts by hand.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from flask import render_template
from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.finance import (
    Account,
    FiscalYear,
    Invoice,
    Transaction,
    TransactionCategory,
)

KINDS = ("asset", "liability", "equity", "income", "expense")
BALANCE_KINDS = ("asset", "liability")
CASH = "1000"
BANK = "1020"
CAPITAL = "2800"
OTHER_INCOME = "3800"
OTHER_EXPENSE = "6900"

# The standard chart for Swiss clubs (Verein), after the KMU chart of
# accounts, cut down to what a club books. Clubs can rename and add accounts.
CHART: tuple[tuple[str, str, str, bool], ...] = (
    ("1000", "Kasse", "asset", True),
    ("1020", "Bank", "asset", True),
    ("1060", "Wertschriften", "asset", False),
    ("1100", "Forderungen", "asset", False),
    ("1300", "Aktive Rechnungsabgrenzung", "asset", False),
    ("1500", "Material und Einrichtungen", "asset", False),
    ("2000", "Verbindlichkeiten", "liability", False),
    ("2300", "Passive Rechnungsabgrenzung", "liability", False),
    ("2400", "Darlehen", "liability", False),
    ("2800", "Vereinsvermögen", "equity", False),
    ("3000", "Mitgliederbeiträge", "income", False),
    ("3100", "Spenden und Gönnerbeiträge", "income", False),
    ("3200", "Sponsoring", "income", False),
    ("3400", "Ertrag Anlässe", "income", False),
    ("3500", "Verkauf und Kiosk", "income", False),
    ("3600", "Beiträge und Subventionen", "income", False),
    ("3800", "Übriger Ertrag", "income", False),
    ("4000", "Material- und Warenaufwand", "expense", False),
    ("4400", "Aufwand Anlässe", "expense", False),
    ("5000", "Entschädigungen", "expense", False),
    ("6000", "Raumaufwand und Miete", "expense", False),
    ("6300", "Versicherungen", "expense", False),
    ("6500", "Verwaltungsaufwand", "expense", False),
    ("6600", "Werbung", "expense", False),
    ("6700", "Verbandsbeiträge", "expense", False),
    ("6800", "Bank- und Finanzaufwand", "expense", False),
    ("6900", "Übriger Aufwand", "expense", False),
)

# A first guess at the account of an existing category, by words in its
# name. Only used when the chart is seeded; the board changes it freely.
_GUESSES: tuple[tuple[tuple[str, ...], str], ...] = (
    # More specific words first: a "Verbandsbeitrag" is a cost, not a fee.
    (("verband", "federation"), "6700"),
    (("mitglied", "member", "beitrag", "fee"), "3000"),
    (("spende", "donat", "gönner"), "3100"),
    (("sponsor",), "3200"),
    (("subvention", "j+s", "gemeinde", "grant"), "3600"),
    (("kiosk", "verkauf", "getränk", "sale"), "3500"),
    (("miete", "raum", "rent", "room"), "6000"),
    (("versicherung", "insurance"), "6300"),
    (("material", "werkzeug", "tool"), "4000"),
    (("werbung", "marketing"), "6600"),
    (("bank", "gebühr", "zins", "fee"), "6800"),
    (("entschädigung", "lohn", "honorar", "salary"), "5000"),
    (("verwaltung", "büro", "porto", "admin", "office"), "6500"),
    (("anlass", "event", "fest", "lager"), "3400"),
)


# ── Chart ───────────────────────────────────────────────────────────────────


def ensure_chart() -> None:
    """Seed the club's chart the first time it is needed, and guess an
    account for each category that has none."""
    if db.session.scalar(select(func.count(Account.id))):
        return
    accounts = {}
    for number, name, kind, money in CHART:
        account = Account(number=number, name=name, kind=kind, is_money=money)
        db.session.add(account)
        accounts[number] = account
    db.session.flush()
    for category in db.session.scalars(select(TransactionCategory)):
        if category.account_id is not None:
            continue
        number = guess_account(category.name)
        if number:
            category.account_id = accounts[number].id
    db.session.flush()


def guess_account(name: str) -> str | None:
    lowered = name.lower()
    for words, number in _GUESSES:
        if any(word in lowered for word in words):
            return number
    return None


def accounts_by_number() -> dict[str, Account]:
    ensure_chart()
    return {a.number: a for a in db.session.scalars(select(Account))}


def account_dict(account: Account) -> dict:
    return {
        "id": account.id,
        "number": account.number,
        "name": account.name,
        "kind": account.kind,
        "isMoney": account.is_money,
    }


def list_chart() -> dict:
    accounts = sorted(accounts_by_number().values(), key=lambda a: a.number)
    categories = db.session.scalars(
        select(TransactionCategory).order_by(TransactionCategory.name)
    ).all()
    return {
        "accounts": [account_dict(a) for a in accounts],
        "categories": [
            {"id": c.id, "name": c.name, "accountId": c.account_id} for c in categories
        ],
    }


def create_account(data: dict) -> Account:
    ensure_chart()
    number = str(data.get("number") or "").strip()
    name = str(data.get("name") or "").strip()
    kind = data.get("kind")
    if not number.isdigit() or len(number) > 10:
        raise_error(400, "VALIDATION_ERROR", "number must be digits")
    if not name or len(name) > 120:
        raise_error(400, "VALIDATION_ERROR", "name is required")
    if kind not in KINDS or kind == "equity":
        raise_error(
            400, "VALIDATION_ERROR", "kind must be asset, liability, income or expense"
        )
    if db.session.scalar(select(Account.id).where(Account.number == number)):
        raise_error(409, "CONFLICT", f"Account {number} exists")
    account = Account(number=number, name=name, kind=kind, is_money=False)
    db.session.add(account)
    db.session.flush()
    return account


def update_account(account: Account, data: dict) -> Account:
    if "name" in data:
        name = str(data.get("name") or "").strip()
        if not name or len(name) > 120:
            raise_error(400, "VALIDATION_ERROR", "name is required")
        account.name = name
    return account


def delete_account(account: Account) -> None:
    if account.number in (CASH, BANK, CAPITAL, OTHER_INCOME, OTHER_EXPENSE):
        raise_error(
            409, "ACCOUNT_REQUIRED", "This account is needed for the annual accounts"
        )
    used = db.session.scalar(
        select(func.count(TransactionCategory.id)).where(
            TransactionCategory.account_id == account.id
        )
    )
    if used:
        raise_error(409, "ACCOUNT_IN_USE", "Categories still count on this account")
    for year in db.session.scalars(select(FiscalYear)):
        if account.number in (year.opening or {}) or account.number in (
            year.closing or {}
        ):
            raise_error(
                409, "ACCOUNT_IN_USE", "A fiscal year has a balance on this account"
            )
    db.session.delete(account)


def map_category(category: TransactionCategory, account_id: int | None) -> None:
    if account_id is not None:
        account = db.session.get(Account, account_id)
        if account is None or account.kind not in ("income", "expense"):
            raise_error(400, "VALIDATION_ERROR", "Pick an income or expense account")
    category.account_id = account_id


# ── Years ───────────────────────────────────────────────────────────────────


def start_month() -> int:
    from hubra.core.modules import get_config

    month = get_config("finance").get("fiscal_year_start_month") or 1
    return month if isinstance(month, int) and 1 <= month <= 12 else 1


def year_bounds(year: int) -> tuple[date, date]:
    """The fiscal year named after the calendar year it starts in."""
    start = date(year, start_month(), 1)
    try:
        end = start.replace(year=start.year + 1) - timedelta(days=1)
    except ValueError:  # pragma: no cover - day 1 always exists
        end = date(year, 12, 31)
    return start, end


def _year_row(start: date) -> FiscalYear | None:
    return db.session.scalar(select(FiscalYear).where(FiscalYear.start == start))


def _closed_before(start: date) -> FiscalYear | None:
    return db.session.scalar(
        select(FiscalYear)
        .where(FiscalYear.start < start, FiscalYear.closed_at.isnot(None))
        .order_by(FiscalYear.start.desc())
        .limit(1)
    )


def _money_account(method: str | None) -> str:
    return CASH if (method or "").lower() == "cash" else BANK


def _money_moves(start: date | None, end: date) -> dict[str, Decimal]:
    """Completed transactions per money account, from *start* (or the very
    beginning) up to and with *end*."""
    query = (
        select(Transaction.method, func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.status == "Completed", Transaction.date <= end)
        .group_by(Transaction.method)
    )
    if start is not None:
        query = query.where(Transaction.date >= start)
    out: dict[str, Decimal] = {CASH: Decimal(0), BANK: Decimal(0)}
    for method, amount in db.session.execute(query):
        out[_money_account(method)] += Decimal(amount)
    return out


def _dec(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def opening_balances(start: date) -> tuple[dict[str, Decimal], str]:
    """The opening balances of the year from *start* (asset and liability
    accounts) and where they come from: "closing" (the closed year before),
    or "computed" (money booked before the year, plus what the board set)."""
    accounts = accounts_by_number()
    previous = _closed_before(start)
    row = _year_row(start)
    if previous is not None and previous.end == start - timedelta(days=1):
        balances = {k: _dec(v) for k, v in (previous.closing or {}).items()}
        source = "closing"
    else:
        balances = {}
        if previous is not None:
            # A gap: carry the last closing and add the money in between.
            balances = {k: _dec(v) for k, v in (previous.closing or {}).items()}
            moves = _money_moves(
                previous.end + timedelta(days=1), start - timedelta(days=1)
            )
        else:
            moves = _money_moves(None, start - timedelta(days=1))
        for number, amount in moves.items():
            balances[number] = balances.get(number, Decimal(0)) + amount
        source = "computed"
        if row is not None:
            for number, amount in (row.opening or {}).items():
                balances[number] = _dec(amount)
    return (
        {
            n: v
            for n, v in balances.items()
            if n in accounts and accounts[n].kind in BALANCE_KINDS
        },
        source,
    )


def set_opening(year: int, values: dict) -> FiscalYear:
    """The board sets opening balances by hand: ``{account number: amount}``.
    Only while the year is open and the year before is not closed."""
    start, end = year_bounds(year)
    previous = _closed_before(start)
    if previous is not None and previous.end == start - timedelta(days=1):
        raise_error(
            409,
            "OPENING_FROM_CLOSING",
            "The opening balances come from the closed year before",
        )
    accounts = accounts_by_number()
    clean: dict[str, str] = {}
    for number, amount in (values or {}).items():
        account = accounts.get(str(number))
        if account is None or account.kind not in BALANCE_KINDS:
            raise_error(
                400, "VALIDATION_ERROR", f"{number} is no asset or liability account"
            )
        try:
            clean[account.number] = str(_dec(amount))
        except (ArithmeticError, ValueError):
            raise_error(400, "VALIDATION_ERROR", f"Amount for {number} is not a number")
    row = _year_row(start)
    if row is None:
        row = FiscalYear(start=start, end=end, opening={})
        db.session.add(row)
    if row.closed_at is not None:
        raise_error(409, "YEAR_CLOSED", "This year is closed")
    row.opening = clean
    db.session.flush()
    return row


# ── Report ──────────────────────────────────────────────────────────────────


def _results(start: date, end: date) -> dict[str, Decimal]:
    """Signed sums per income or expense account number for the period."""
    accounts = {a.id: a for a in accounts_by_number().values()}
    rows = db.session.execute(
        select(
            TransactionCategory.account_id,
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .select_from(Transaction)
        .outerjoin(
            TransactionCategory, Transaction.category_id == TransactionCategory.id
        )
        .where(
            Transaction.status == "Completed",
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(TransactionCategory.account_id, Transaction.type)
    ).all()
    out: dict[str, Decimal] = {}
    for account_id, kind, amount in rows:
        account = accounts.get(account_id)
        if account is not None and account.kind in ("income", "expense"):
            number = account.number
        else:
            number = OTHER_EXPENSE if kind == "expense" else OTHER_INCOME
        out[number] = out.get(number, Decimal(0)) + Decimal(amount)
    return out


def _report(year: int) -> dict:
    start, end = year_bounds(year)
    accounts = accounts_by_number()
    opening, source = opening_balances(start)
    results = _results(start, end)
    moves = _money_moves(start, end)

    income = {n: v for n, v in results.items() if accounts[n].kind == "income"}
    # Expenses are stored negative; the statement shows them positive.
    expense = {n: -v for n, v in results.items() if accounts[n].kind == "expense"}
    result = sum(income.values(), Decimal(0)) - sum(expense.values(), Decimal(0))

    closing = dict(opening)
    for number, amount in moves.items():
        closing[number] = closing.get(number, Decimal(0)) + amount

    def side(balances: dict[str, Decimal], kind: str) -> dict[str, Decimal]:
        return {n: v for n, v in balances.items() if accounts[n].kind == kind and v}

    open_assets = sum(side(opening, "asset").values(), Decimal(0))
    open_liabilities = sum(side(opening, "liability").values(), Decimal(0))
    capital_open = open_assets - open_liabilities
    return {
        "start": start,
        "end": end,
        "opening": opening,
        "openingSource": source,
        "income": income,
        "expense": expense,
        "result": result,
        "assets": side(closing, "asset"),
        "liabilities": side(closing, "liability"),
        "capitalOpen": capital_open,
        "capitalClose": capital_open + result,
        "closing": closing,
    }


def _lines(
    values: dict[str, Decimal], previous: dict[str, Decimal] | None
) -> list[dict]:
    accounts = accounts_by_number()
    numbers = sorted(set(values) | set(previous or {}))
    return [
        {
            "number": n,
            "name": accounts[n].name,
            "amount": float(values.get(n, 0)),
            "previous": float((previous or {}).get(n, 0))
            if previous is not None
            else None,
        }
        for n in numbers
        if values.get(n) or (previous or {}).get(n)
    ]


def _has_bookings(start: date, end: date) -> bool:
    return bool(
        db.session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.date >= start, Transaction.date <= end
            )
        )
    )


def annual_report(year: int) -> dict:
    """The annual accounts of fiscal year *year*, with the year before for
    comparison when it has bookings or is closed."""
    now = _report(year)
    start, end = now["start"], now["end"]
    prev_start, prev_end = year_bounds(year - 1)
    prev = None
    prev_row = _year_row(prev_start)
    if _has_bookings(prev_start, prev_end) or (prev_row and prev_row.closed_at):
        prev = _report(year - 1)
    row = _year_row(start)
    open_invoices = db.session.execute(
        select(
            func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0)
        ).where(Invoice.status != "Paid", Invoice.issued <= end)
    ).one()
    unmapped = db.session.scalar(
        select(func.count(Transaction.id))
        .outerjoin(
            TransactionCategory, Transaction.category_id == TransactionCategory.id
        )
        .where(
            Transaction.status == "Completed",
            Transaction.date >= start,
            Transaction.date <= end,
            TransactionCategory.account_id.is_(None),
        )
    )
    pending = db.session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.status == "Pending",
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )
    accounts = accounts_by_number()
    capital = accounts[CAPITAL].name
    return {
        "year": year,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "closed": bool(row and row.closed_at),
        "closedAt": row.closed_at.isoformat() if row and row.closed_at else None,
        "openingSource": now["openingSource"],
        "opening": [
            {
                "number": n,
                "name": accounts[n].name,
                "kind": accounts[n].kind,
                "amount": float(v),
            }
            for n, v in sorted(now["opening"].items())
        ],
        "hasPrevious": prev is not None,
        "income": _lines(now["income"], prev and prev["income"]),
        "expense": _lines(now["expense"], prev and prev["expense"]),
        "totalIncome": float(sum(now["income"].values(), Decimal(0))),
        "totalExpense": float(sum(now["expense"].values(), Decimal(0))),
        "result": float(now["result"]),
        "previousResult": float(prev["result"]) if prev else None,
        "assets": _lines(now["assets"], prev and prev["assets"]),
        "liabilities": _lines(now["liabilities"], prev and prev["liabilities"]),
        "capital": {
            "number": CAPITAL,
            "name": capital,
            "opening": float(now["capitalOpen"]),
            "closing": float(now["capitalClose"]),
            "previous": float(prev["capitalClose"]) if prev else None,
        },
        "totalAssets": float(sum(now["assets"].values(), Decimal(0))),
        "notes": {
            "openInvoices": {
                "count": open_invoices[0] or 0,
                "amount": float(open_invoices[1] or 0),
            },
            "unmappedBookings": unmapped or 0,
            "pendingBookings": pending or 0,
        },
    }


def years_overview() -> list[dict]:
    """Years with bookings or a stored row, newest first."""
    first = db.session.scalar(select(func.min(Transaction.date)))
    today = date.today()
    current = today.year if today >= year_bounds(today.year)[0] else today.year - 1
    oldest = current
    if first is not None:
        oldest = first.year if first >= year_bounds(first.year)[0] else first.year - 1
    stored = {r.start: r for r in db.session.scalars(select(FiscalYear))}
    for start in stored:
        oldest = min(oldest, start.year)
    out = []
    for year in range(current, oldest - 1, -1):
        start, end = year_bounds(year)
        row = stored.get(start)
        out.append(
            {
                "year": year,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "closed": bool(row and row.closed_at),
            }
        )
    return out


# ── Close ───────────────────────────────────────────────────────────────────


def close_year(year: int, member_id: int | None) -> FiscalYear:
    """Store the closing balances and lock the year's bookings. The year
    before must be closed first, unless this is the first year."""
    start, end = year_bounds(year)
    if end >= date.today():
        raise_error(409, "YEAR_NOT_OVER", "The year is not over yet")
    prev_start, _ = year_bounds(year - 1)
    prev_row = _year_row(prev_start)
    if prev_row is not None and prev_row.closed_at is None:
        raise_error(409, "PREVIOUS_YEAR_OPEN", "Close the year before first")
    if prev_row is None and _has_bookings(*year_bounds(year - 1)):
        raise_error(409, "PREVIOUS_YEAR_OPEN", "Close the year before first")
    report = _report(year)
    row = _year_row(start)
    if row is None:
        row = FiscalYear(start=start, end=end, opening={})
        db.session.add(row)
    if row.closed_at is not None:
        raise_error(409, "YEAR_CLOSED", "This year is already closed")
    row.opening = {n: str(v) for n, v in report["opening"].items()}
    row.closing = {n: str(v) for n, v in report["closing"].items() if v}
    row.closing[CAPITAL] = str(report["capitalClose"])
    row.closed_at = datetime.now(timezone.utc)
    row.closed_by = member_id
    db.session.flush()
    return row


def reopen_year(year: int) -> FiscalYear:
    start, _ = year_bounds(year)
    row = _year_row(start)
    if row is None or row.closed_at is None:
        raise_error(409, "YEAR_OPEN", "This year is not closed")
    next_start, _ = year_bounds(year + 1)
    following = _year_row(next_start)
    if following is not None and following.closed_at is not None:
        raise_error(409, "NEXT_YEAR_CLOSED", "Reopen the year after first")
    row.closing = None
    row.closed_at = None
    row.closed_by = None
    db.session.flush()
    return row


def closed_on(day: date) -> bool:
    return bool(
        db.session.scalar(
            select(func.count(FiscalYear.id)).where(
                FiscalYear.closed_at.isnot(None),
                FiscalYear.start <= day,
                FiscalYear.end >= day,
            )
        )
    )


@event.listens_for(Session, "before_flush")
def _guard_closed_years(session, _flush_context, _instances) -> None:
    """No booking is added, changed or removed in a closed year, from any
    path (forms, invoices, imports, plugins)."""
    from hubra.core.errors import ApiError

    days: set[date] = set()
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if not isinstance(obj, Transaction):
            continue
        if obj in session.dirty and not session.is_modified(
            obj, include_collections=False
        ):
            continue
        if obj.date is not None:
            days.add(obj.date)
        history = inspect(obj).attrs.date.history
        days.update(d for d in (history.deleted or ()) if d is not None)
    if not days:
        return
    with session.no_autoflush:
        closed = session.execute(
            select(FiscalYear.start, FiscalYear.end).where(
                FiscalYear.closed_at.isnot(None)
            )
        ).all()
    for day in days:
        if any(s <= day <= e for s, e in closed):
            raise ApiError(
                409,
                "YEAR_CLOSED",
                f"The fiscal year of {day.isoformat()} is closed",
            )


# ── PDF ─────────────────────────────────────────────────────────────────────


def annual_pdf(report: dict, lang: str) -> bytes:
    from weasyprint import HTML

    from hubra.api.finance.statement import chf
    from hubra.core.services.email import club_display_name
    from hubra.core.services.mail_format import mail_date
    from hubra.core.services.mail_i18n import get_mail_translator
    from hubra.core.services.qr_bill import _no_fetch

    html = render_template(
        "finance/annual.html",
        t=get_mail_translator(lang),
        lang=lang,
        r=report,
        club=club_display_name(),
        chf=chf,
        fmt_date=lambda day: mail_date(date.fromisoformat(day), lang),
        created=mail_date(date.today(), lang),
    )
    return HTML(string=html, url_fetcher=_no_fetch()).write_pdf()
