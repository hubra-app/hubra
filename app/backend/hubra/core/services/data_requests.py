"""Data protection requests per club: a copy of someone's data, or deleting
it, and the record of when and how each was handled.

Hubra hosts the clubs, so a person who wants their data or wants it gone
often writes to the platform (or the club passes the request on).  Manage
records the request (``models.DataRequest``), the deadline (30 days, as
GDPR art. 12(3) and the Swiss nDSG expect), and then:

* **export**: a JSON file with everything the club holds about the member:
  their account details the club sees, the member row and every club row
  that points at the member (found from the foreign keys to ``members``,
  so new modules are covered without a change here).  Each download is
  noted on the request and in the platform log.
* **deletion**: the member leaves the club and is deleted the way a club
  admin deletes an archived member (``MemberService.delete_permanent``):
  their own rows go, invoices and bookings stay without the name (the
  club has to keep its books), audit entries lose the actor.  The Hubra
  account stays: clubs never delete accounts, the person does that.

Then the request is marked done (or rejected, with the reason) with who
did it and when.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.data_request import DataRequest
from hubra.core.models.tenant import Tenant

KINDS = ("export", "deletion")
STATUSES = ("open", "done", "rejected")
DUE_DAYS = 30
SOON_DAYS = 7

# Never in an export: secrets and sign-in state, not personal data the
# person gave the club.
_SECRET = re.compile(
    r"password|secret|token|hash|recovery|totp|otp_|_key$|^key$|"
    r"failed_login|locked_until|tokens_valid_after|is_superadmin|nav_prefs|"
    r"platform_alerts"
)
_ACCOUNT_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "phone",
    "mobile",
    "birthday",
    "gender",
    "address_street",
    "address_house_no",
    "address_postal_code",
    "address_city",
    "address_country",
    "emergency_contact",
    "profile_note",
    "language",
    "created_at",
)


def _bad(msg: str, status: int = 400, code: str = "VALIDATION_ERROR"):
    raise ApiError(status, code, msg)


def _text(body: dict, key: str, limit: int, required: bool = False) -> str:
    value = body.get(key)
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit:
        _bad(f"{key} is text up to {limit} characters")
    value = value.strip()
    if required and not value:
        _bad(f"{key} is needed")
    return value


def _date(value, key: str) -> date:
    if not isinstance(value, str):
        _bad(f"{key} is a date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _bad(f"{key} is a date (YYYY-MM-DD)")


# ── Requests ─────────────────────────────────────────────────────────────────


def create(tenant: Tenant, body: dict, actor_id: int, today: date | None = None):
    """Record a new request.  Does NOT commit."""
    if not isinstance(body, dict):
        _bad("Send an object")
    kind = body.get("kind")
    if kind not in KINDS:
        _bad("kind is export or deletion")
    today = today or date.today()
    received = (
        _date(body["received_on"], "received_on") if body.get("received_on") else today
    )
    if received > today:
        _bad("received_on cannot be in the future")
    name = _text(body, "subject_name", 200)
    email = _text(body, "subject_email", 320)
    member_id = _member_id(tenant, body.get("member_id"))
    if not (name or email or member_id):
        _bad("Say who asked: a name, an address or the member")
    req = DataRequest(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        kind=kind,
        status="open",
        subject_name=name,
        subject_email=email,
        member_id=member_id,
        received_on=received,
        received_via=_text(body, "received_via", 100),
        due_on=received + timedelta(days=DUE_DAYS),
        note=_text(body, "note", 2000),
        created_by=actor_id,
    )
    db.session.add(req)
    db.session.flush()
    return req


def update(req: DataRequest, body: dict) -> None:
    """Change who asked, the member or the note of an open request."""
    if req.status != "open":
        _bad("The request is closed", 409, "CLOSED")
    if not isinstance(body, dict):
        _bad("Send an object")
    unknown = set(body) - {"subject_name", "subject_email", "member_id", "note"}
    if unknown:
        _bad(f"Unknown field: {', '.join(sorted(unknown))}")
    if "subject_name" in body:
        req.subject_name = _text(body, "subject_name", 200)
    if "subject_email" in body:
        req.subject_email = _text(body, "subject_email", 320)
    if "note" in body:
        req.note = _text(body, "note", 2000)
    if "member_id" in body:
        req.member_id = _member_id(_tenant(req), body["member_id"])


def close(req: DataRequest, status: str, outcome: str, actor_id: int) -> None:
    """Mark the request done or rejected.  Does NOT commit."""
    if req.status != "open":
        _bad("The request is closed", 409, "CLOSED")
    if status == "rejected" and not outcome:
        _bad("Say why the request is rejected")
    if (
        status == "done"
        and req.kind == "deletion"
        and not (req.result or {}).get("deleted")
    ):
        _bad(
            "Delete the member's data first, or reject the request",
            409,
            "NOT_DELETED",
        )
    req.status = status
    req.outcome = outcome
    req.handled_at = datetime.now(timezone.utc)
    req.handled_by = actor_id


def _tenant(req: DataRequest) -> Tenant:
    tenant = db.session.get(Tenant, req.tenant_id)
    if tenant is None:
        _bad("The club no longer exists", 409, "NO_CLUB")
    return tenant


def _member_id(tenant: Tenant, value) -> int | None:
    if value in (None, ""):
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        _bad("member_id is a member's number")
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import in_club

    with in_club(tenant):
        if db.session.get(Member, value) is None:
            _bad("No such member in this club", 404, "NOT_FOUND")
    return value


def _user_name(user_id: int | None, cache: dict) -> str | None:
    if user_id is None:
        return None
    if user_id not in cache:
        from hubra.core.models.user import User

        user = db.session.get(User, user_id)
        cache[user_id] = user.name if user else None
    return cache[user_id]


def to_dict(
    req: DataRequest, today: date | None = None, names: dict | None = None
) -> dict:
    today = today or date.today()
    names = {} if names is None else names
    days_left = (req.due_on - today).days if req.status == "open" else None
    return {
        "id": req.id,
        "tenant_id": req.tenant_id,
        "tenant_name": req.tenant_name,
        "kind": req.kind,
        "status": req.status,
        "subject_name": req.subject_name,
        "subject_email": req.subject_email,
        "member_id": req.member_id,
        "received_on": req.received_on.isoformat(),
        "received_via": req.received_via,
        "due_on": req.due_on.isoformat(),
        "days_left": days_left,
        "overdue": days_left is not None and days_left < 0,
        "due_soon": days_left is not None and 0 <= days_left <= SOON_DAYS,
        "note": req.note,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "created_by": req.created_by,
        "created_by_name": _user_name(req.created_by, names),
        "handled_at": req.handled_at.isoformat() if req.handled_at else None,
        "handled_by": req.handled_by,
        "handled_by_name": _user_name(req.handled_by, names),
        "outcome": req.outcome,
        "result": req.result,
        "exports": req.exports or [],
    }


def listing(status: str = "open", tenant_id: int | None = None) -> dict:
    """Requests, open ones by deadline first, with the counts for the badge."""
    q = select(DataRequest)
    if tenant_id is not None:
        q = q.where(DataRequest.tenant_id == tenant_id)
    if status != "all":
        q = q.where(DataRequest.status == status)
    q = q.order_by(
        (DataRequest.status != "open"),
        DataRequest.due_on,
        DataRequest.id.desc(),
    ).limit(500)
    rows = db.session.scalars(q).all()
    names: dict = {}
    today = date.today()
    return {
        "requests": [to_dict(r, today, names) for r in rows],
        "counts": counts(tenant_id),
    }


def counts(tenant_id: int | None = None) -> dict:
    q = select(func.count()).where(DataRequest.status == "open")
    if tenant_id is not None:
        q = q.where(DataRequest.tenant_id == tenant_id)
    today = date.today()
    return {
        "open": db.session.scalar(q) or 0,
        "overdue": db.session.scalar(q.where(DataRequest.due_on < today)) or 0,
    }


# ── Export ───────────────────────────────────────────────────────────────────


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def _row(obj) -> dict:
    """An ORM row's columns, decrypted, without secrets."""
    return {
        attr.key: _plain(getattr(obj, attr.key))
        for attr in obj.__mapper__.column_attrs
        if not _SECRET.search(attr.key)
    }


def _member_tables() -> list[tuple]:
    """(table, column) for every club column that points at a member."""
    from hubra.core.tenant.schema_manager import tables_to_clone

    club_tables = set(tables_to_clone())
    out = []
    for table in db.metadata.sorted_tables:
        if table.name not in club_tables or table.name == "members":
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name == "members":
                out.append((table, fk.parent))
    return out


def export_member(tenant: Tenant, member_id: int) -> dict:
    """Everything the club holds about one member, as plain JSON."""
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import in_club

    classes = {m.local_table.name: m.class_ for m in db.Model.registry.mappers}
    with in_club(tenant):
        member = db.session.get(Member, member_id)
        if member is None:
            _bad("No such member in this club", 404, "NOT_FOUND")
        user = member.user
        account = (
            {k: _plain(getattr(user, k, None)) for k in _ACCOUNT_FIELDS}
            if user is not None
            else None
        )
        related: dict[str, list] = {}
        for table, column in _member_tables():
            cls = classes.get(table.name)
            if cls is not None and cls.__table__ is table:
                rows = [
                    _row(r)
                    for r in db.session.scalars(
                        select(cls).where(column == member_id)
                    ).all()
                ]
            else:
                rows = [
                    {
                        k: _plain(v)
                        for k, v in r._mapping.items()
                        if not _SECRET.search(k)
                    }
                    for r in db.session.execute(
                        select(table).where(column == member_id)
                    ).all()
                ]
            if rows:
                key = (
                    table.name
                    if column.name == "member_id"
                    else f"{table.name}.{column.name}"
                )
                related.setdefault(key, []).extend(rows)
        from hubra.core.contracts import privacy

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club": {"name": tenant.name, "slug": tenant.slug},
            "account": account,
            "member": _row(member),
            "related": related,
            # What modules keep beyond their foreign-key rows
            # (<module>.privacy.export contracts).
            "modules": privacy.export(member_id),
        }
    return data


def record_export(req: DataRequest, data: dict, actor_id: int) -> None:
    exports = list(req.exports or [])
    exports.append({"at": datetime.now(timezone.utc).isoformat(), "by": actor_id})
    req.exports = exports
    req.result = {
        "rows": {k: len(v) for k, v in data["related"].items()},
        "exported_at": exports[-1]["at"],
    }


# ── Deletion ─────────────────────────────────────────────────────────────────


def delete_member(req: DataRequest, actor_id: int) -> set[int]:
    """Take the member out of the club and delete their club data.

    Returns the groups to resync once committed.  Does NOT commit.
    """
    from hubra.api.members.services import MemberService
    from hubra.core.utils import log_audit
    from hubra.core.models.finance import Invoice, Transaction
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import in_club

    if req.kind != "deletion":
        _bad("Only a deletion request deletes", 409, "WRONG_KIND")
    if req.status != "open":
        _bad("The request is closed", 409, "CLOSED")
    if req.member_id is None:
        _bad("Choose the member first")
    tenant = _tenant(req)
    affected: set[int] = set()
    with in_club(tenant):
        member = db.session.get(Member, req.member_id)
        if member is None:
            _bad("No such member in this club", 404, "NOT_FOUND")
        kept = {
            "invoices": db.session.scalar(
                select(func.count()).where(Invoice.member_id == member.id)
            )
            or 0,
            "transactions": db.session.scalar(
                select(func.count()).where(Transaction.member_id == member.id)
            )
            or 0,
        }
        if member.archived_at is None:
            affected = MemberService.leave(member)  # 409 for the last owner
        elif member.user_id is not None:
            from hubra.core.models.user_tenant import UserTenant

            db.session.query(UserTenant).filter_by(
                user_id=member.user_id, tenant_id=tenant.id
            ).delete()
        db.session.flush()
        # actor 0: no member of the club did this; it was the platform.
        MemberService.delete_permanent(member.id, 0)
        log_audit(
            actor_id=None,
            action="privacy_deletion",
            target_type="Member",
            target_id=member.id,
            target_label=f"#{member.id}",
        )
        db.session.delete(member)
        db.session.flush()
    req.result = {
        "deleted": True,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_by": actor_id,
        "kept_without_name": kept,
    }
    return affected


# ── Retention ────────────────────────────────────────────────────────────────


def purge_former_members(tenant: Tenant, years: int, now: datetime | None = None) -> dict:
    """Delete members who left the club more than *years* ago.

    Runs inside the club (the daily job).  A former member is an archived
    one (``archived_at``); they are deleted like a deletion request:
    their own rows go, invoices and bookings stay without the name.  A
    member something still depends on (a binding, a club address) is
    skipped and counted.  Commits after each member, so one that fails
    does not undo the others.
    """
    from hubra.api.members.services import MemberService
    from hubra.core.models.member import Member
    from hubra.core.utils import log_audit

    now = now or datetime.now(timezone.utc)
    # Calendar years back, on 28 Feb for a 29 Feb.
    try:
        cutoff = now.replace(year=now.year - years)
    except ValueError:
        cutoff = now.replace(year=now.year - years, day=28)
    ids = db.session.scalars(
        select(Member.id)
        .where(Member.archived_at.isnot(None))
        .where(Member.archived_at < cutoff)
        .order_by(Member.id)
    ).all()
    deleted = skipped = 0
    for member_id in ids:
        try:
            member = MemberService.delete_permanent(member_id, 0)
            log_audit(
                actor_id=None,
                action="privacy_retention_deletion",
                target_type="Member",
                target_id=member_id,
                target_label=f"#{member_id}",
            )
            db.session.delete(member)
            db.session.commit()
            deleted += 1
        except ApiError:
            db.session.rollback()
            skipped += 1
    return {"deleted": deleted, "skipped": skipped, "tenant": tenant.slug}
