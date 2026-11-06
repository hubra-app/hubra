"""Data protection self-service for members (revDSG / GDPR).

What a member does for themselves on Account › Membership:

* **consents**: photos (``members.photo_consent``) and what they show in the
  directory (``members.directory_shared``). Each change is logged in
  ``member_consents`` with who changed it and when.
* **a copy of their data**: the same JSON export manage makes
  (``data_requests.export_member``), downloaded straight away. The download
  is recorded as a finished export request, so the platform's list of data
  requests shows it too.
* **asking for deletion**: an open deletion request in manage's queue
  (``models.DataRequest``), with the usual 30-day deadline. The platform
  deletes the club data the way it does for any deletion request.

And for the club: ``retention_years`` (Settings › Club, off by default)
deletes former members a number of years after they left, see
``data_requests.purge_former_members``.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.consent import CONSENT_KINDS, MemberConsent
from hubra.core.models.data_request import DataRequest
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.tenant.club_settings import club_setting

SELF_SERVICE = "self-service"
RETENTION_MIN_YEARS = 1
RETENTION_MAX_YEARS = 30


def retention_years(tenant: Tenant | None) -> int | None:
    """Years after leaving that former members are deleted, or None (off)."""
    value = club_setting(tenant, "former_member_retention_years")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not RETENTION_MIN_YEARS <= value <= RETENTION_MAX_YEARS:
        return None
    return value


def log_consent(
    member: Member, kind: str, value, changed_by: int | None, source: str = "self"
) -> MemberConsent:
    """Record a consent change.  Does NOT commit."""
    if kind not in CONSENT_KINDS:
        raise ValueError(kind)
    row = MemberConsent(
        member_id=member.id,
        kind=kind,
        value=value,
        changed_by=changed_by,
        source=source,
    )
    db.session.add(row)
    return row


def set_photo_consent(
    member: Member, value: bool, changed_by: int | None, source: str = "self"
) -> bool:
    """Change the photo consent; True when it changed.  Does NOT commit."""
    if member.photo_consent is value:
        return False
    member.photo_consent = value
    log_consent(member, "photos", value, changed_by, source)
    return True


def consent_log(member_id: int, limit: int = 100) -> list[dict]:
    rows = db.session.scalars(
        select(MemberConsent)
        .where(MemberConsent.member_id == member_id)
        .order_by(MemberConsent.created_at.desc(), MemberConsent.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "kind": r.kind,
            "value": r.value,
            "source": r.source,
            "changed_by": r.changed_by,
            "at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def _open_deletion(tenant: Tenant, member_id: int) -> DataRequest | None:
    return db.session.scalar(
        select(DataRequest)
        .where(DataRequest.tenant_id == tenant.id)
        .where(DataRequest.member_id == member_id)
        .where(DataRequest.kind == "deletion")
        .where(DataRequest.status == "open")
        .order_by(DataRequest.id.desc())
        .limit(1)
    )


def _subject(member: Member) -> tuple[str, str]:
    user = member.user
    if user is None:
        return "", ""
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    return name[:200], (user.email or "")[:320]


def overview(tenant: Tenant, member: Member) -> dict:
    """The member's privacy page: consents, an open deletion request, the
    club's retention rule and the consent history."""
    req = _open_deletion(tenant, member.id)
    return {
        "photo_consent": member.photo_consent,
        "directory_shared": list(member.directory_shared or []),
        "deletion_request": (
            {
                "received_on": req.received_on.isoformat(),
                "due_on": req.due_on.isoformat(),
            }
            if req is not None
            else None
        ),
        "retention_years": retention_years(tenant),
        "log": consent_log(member.id, limit=20),
    }


def export_own(tenant: Tenant, member: Member) -> dict:
    """The member's data as JSON, recorded as a finished export request.
    Does NOT commit."""
    from datetime import datetime, timezone

    from hubra.core.services import data_requests

    data = data_requests.export_member(tenant, member.id)
    name, email = _subject(member)
    today = date.today()
    req = DataRequest(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        kind="export",
        status="done",
        subject_name=name,
        subject_email=email,
        member_id=member.id,
        received_on=today,
        received_via=SELF_SERVICE,
        due_on=today,
        note="",
        created_by=member.user_id,
        handled_at=datetime.now(timezone.utc),
        handled_by=member.user_id,
        outcome="Downloaded by the member (Account › Membership).",
    )
    db.session.add(req)
    data_requests.record_export(req, data, member.user_id or 0)
    return data


def request_deletion(tenant: Tenant, member: Member, note: str = "") -> DataRequest:
    """An open deletion request in manage's queue.  Does NOT commit."""
    from hubra.core.services.data_requests import DUE_DAYS

    if _open_deletion(tenant, member.id) is not None:
        raise ApiError(409, "DELETION_REQUESTED", "You already asked for deletion")
    name, email = _subject(member)
    today = date.today()
    req = DataRequest(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        kind="deletion",
        status="open",
        subject_name=name,
        subject_email=email,
        member_id=member.id,
        received_on=today,
        received_via=SELF_SERVICE,
        due_on=today + timedelta(days=DUE_DAYS),
        note=(note or "")[:2000],
        created_by=member.user_id,
    )
    db.session.add(req)
    db.session.flush()
    return req
