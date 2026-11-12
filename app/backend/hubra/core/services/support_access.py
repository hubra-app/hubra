"""Support access as the club sees it.

When Hubra staff open a club as one of its members (manage › club › "Open
as admin", ``/tenants/<id>/impersonate``), the club's own audit log gets an
entry at the start (who, which member, why, how long, looking or changing)
and at the end. The platform keeps its own log (``GlobalAuditEntry``,
manage › Support access); these entries are the club's copy.

A club can require approval first (club setting
``support_requires_approval``): staff then ask from manage, the club's
admins get a notification and approve or decline in the club app
(Settings › Club), and an approval can start one session within
``APPROVAL_HOURS``, by the staff member who asked, with the reason, length
and mode they asked for.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.audit import AuditEntry
from hubra.core.models.support_access import SupportAccessRequest
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User

SETTING = "support_requires_approval"
APPROVAL_HOURS = 24
REASON_MAX = 500
# Nobody holds this key: only the club's admins hear about requests.
_ADMINS_ONLY = "support.access.approve"


class SupportAccessError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def requires_approval(tenant: Tenant) -> bool:
    from hubra.core.tenant.club_settings import club_setting

    return bool(club_setting(tenant, SETTING, False))


def staff_name(user: User | None) -> str:
    if user is None:
        return "Hubra support"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return f"Hubra support · {name}" if name else "Hubra support"


def _log(
    tenant: Tenant,
    staff: User | None,
    action: str,
    label: str,
    *,
    actor_id: int | None = None,
    actor_name: str | None = None,
) -> None:
    """One entry in the club's audit log (its own schema). The actor is
    Hubra support, or the club admin who decided (*actor_id*/*actor_name*)."""
    from hubra.core.tenant.context import in_club

    if len(label) > 255:
        label = label[:254] + "…"
    with in_club(tenant):
        db.session.add(
            AuditEntry(
                actor_id=actor_id,
                actor_name=actor_name or staff_name(staff),
                action=action,
                target_type="Support",
                target_id=None,
                target_label=label,
                color="orange",
            )
        )
        db.session.flush()


def _label(member_name: str | None, minutes: int | None, reason: str | None) -> str:
    parts = [
        p for p in (member_name, f"{minutes} min" if minutes else None, reason) if p
    ]
    return " · ".join(parts)


def _member_name(tenant: Tenant, member_id) -> str | None:
    from hubra.core.models.member import Member
    from hubra.core.tenant.context import in_club

    if not str(member_id or "").isdigit():
        return None
    with in_club(tenant):
        member = db.session.get(Member, int(member_id))
        return member.name if member is not None else None


def log_start(
    tenant: Tenant,
    staff: User | None,
    member_id,
    *,
    minutes: int,
    reason: str,
    allow_changes: bool,
) -> None:
    """A support session started: in the club's log, in the caller's
    transaction."""
    action = "support_session_change" if allow_changes else "support_session_view"
    _log(
        tenant, staff, action, _label(_member_name(tenant, member_id), minutes, reason)
    )


def log_end(
    tenant: Tenant, staff: User | None, member_id, *, ended_by_platform: bool
) -> None:
    """A support session ended: stopped by the staff member, or ended early
    from manage › Support access (*ended_by_platform*)."""
    _log(
        tenant,
        staff,
        "support_session_revoked" if ended_by_platform else "support_session_end",
        _label(_member_name(tenant, member_id), None, None),
    )


# ── Approval ────────────────────────────────────────────────────────────────


def as_dict(req: SupportAccessRequest, *, staff: User | None = None) -> dict:
    if staff is None:
        staff = db.session.get(User, req.user_id)
    return {
        "id": req.id,
        "staff": staff_name(staff).removeprefix("Hubra support · ") if staff else None,
        "reason": req.reason,
        "minutes": req.minutes,
        "allowChanges": req.allow_changes,
        "status": _status(req),
        "decidedBy": req.decided_by,
        "decidedAt": req.decided_at.isoformat() if req.decided_at else None,
        "createdAt": req.created_at.isoformat() if req.created_at else None,
    }


def _expired(req: SupportAccessRequest, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    since = req.decided_at if req.status == "approved" else req.created_at
    if since is None:
        return False
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return now - since > timedelta(hours=APPROVAL_HOURS)


def _status(req: SupportAccessRequest) -> str:
    """pending | approved | declined | used | expired."""
    if req.status in ("pending", "approved") and _expired(req):
        return "expired"
    return req.status


def ask(
    tenant: Tenant, staff: User, *, reason: str, minutes: int, allow_changes: bool
) -> SupportAccessRequest:
    """Staff ask the club for a support session. Commits."""
    from hubra.core.notifications.staff import notify_permitted
    from hubra.core.tenant.context import in_club

    reason = (reason or "").strip()[:REASON_MAX]
    open_one = db.session.scalar(
        select(SupportAccessRequest)
        .where(SupportAccessRequest.tenant_id == tenant.id)
        .where(SupportAccessRequest.user_id == staff.id)
        .where(SupportAccessRequest.status == "pending")
        .order_by(SupportAccessRequest.id.desc())
        .limit(1)
    )
    if open_one is not None and not _expired(open_one):
        raise SupportAccessError("ALREADY_ASKED", "You already asked this club")
    req = SupportAccessRequest(
        tenant_id=tenant.id,
        user_id=staff.id,
        reason=reason,
        minutes=minutes,
        allow_changes=allow_changes,
        status="pending",
    )
    db.session.add(req)
    _log(tenant, staff, "support_access_request", _label(None, minutes, reason))
    with in_club(tenant):
        notify_permitted(
            _ADMINS_ONLY,
            "warning",
            "Hubra support asks for access",
            reason,
            link="/app/settings/club",
        )
    db.session.commit()
    return req


def for_club(tenant: Tenant, limit: int = 20) -> list[SupportAccessRequest]:
    return list(
        db.session.scalars(
            select(SupportAccessRequest)
            .where(SupportAccessRequest.tenant_id == tenant.id)
            .order_by(SupportAccessRequest.id.desc())
            .limit(limit)
        ).all()
    )


def latest_for(tenant: Tenant, staff_id: int) -> SupportAccessRequest | None:
    return db.session.scalar(
        select(SupportAccessRequest)
        .where(SupportAccessRequest.tenant_id == tenant.id)
        .where(SupportAccessRequest.user_id == staff_id)
        .order_by(SupportAccessRequest.id.desc())
        .limit(1)
    )


def decide(
    tenant: Tenant,
    request_id: int,
    *,
    approve: bool,
    by: str,
    by_member_id: int | None = None,
) -> SupportAccessRequest:
    """A club admin approves or declines. Commits."""
    req = db.session.get(SupportAccessRequest, request_id)
    if req is None or req.tenant_id != tenant.id:
        raise SupportAccessError("NOT_FOUND", "No such request", 404)
    if _status(req) != "pending":
        raise SupportAccessError("ALREADY_DECIDED", "This request is no longer open")
    req.status = "approved" if approve else "declined"
    req.decided_by = by[:255]
    req.decided_at = datetime.now(timezone.utc)
    staff = db.session.get(User, req.user_id)
    _log(
        tenant,
        staff,
        "support_access_approve" if approve else "support_access_decline",
        _label(
            staff_name(staff).removeprefix("Hubra support · "), req.minutes, req.reason
        ),
        actor_id=by_member_id,
        actor_name=by,
    )
    db.session.commit()
    return req


def take_approval(tenant: Tenant, staff_id: int, request_id) -> SupportAccessRequest:
    """The approved request *staff_id* may start a session with; marks it
    used (in the caller's transaction)."""
    if not str(request_id or "").isdigit():
        raise SupportAccessError(
            "SUPPORT_APPROVAL_REQUIRED",
            "This club approves support sessions first: ask the club",
            403,
        )
    req = db.session.get(SupportAccessRequest, int(request_id))
    if (
        req is None
        or req.tenant_id != tenant.id
        or req.user_id != staff_id
        or _status(req) != "approved"
    ):
        raise SupportAccessError(
            "SUPPORT_APPROVAL_REQUIRED",
            "No approval from the club for this session",
            403,
        )
    req.status = "used"
    return req
