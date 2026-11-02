"""Deciding club requests: approve (the club is set up) or reject.

Used by manage (``/api/v1/manager/tenant-requests/<id>/approve|reject``)
and by the Approve / Reject buttons on the request's message in the
platform's Discord log (``platform_bot``).  The caller checks the
``requests.approve`` permission.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.models.tenant_request import TenantRequest
from hubra.core.models.user import User

_log = logging.getLogger(__name__)


class RequestDecisionError(Exception):
    """The request cannot be decided (``status``: HTTP status, ``code``)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def audit(action: str, req: TenantRequest, actor_id, ip: str | None = None, **details):
    """Club requests are platform events too (and go to the platform log).
    No commit."""
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=int(actor_id) if actor_id else None,
            action=f"tenant_request.{action}",
            target_type="TenantRequest",
            target_id=str(req.id),
            details={"name": req.name, "slug": req.slug, "plan": req.plan, **details},
            ip_address=ip,
        )
    )


def notify_requester(req: TenantRequest) -> bool:
    """Mail the requester that *req* was approved or rejected.  True when sent.

    The decision is already committed: a mail failure is logged, never raised.
    """
    from hubra.core.services import email as email_svc

    user = db.session.get(User, req.user_id)
    if user is None or not user.email:
        return False
    lang = user.language or "de-CH"
    try:
        if req.status == "approved":
            return email_svc.send_club_request_approved(
                user.email, user.name, req.name, lang=lang
            )
        return email_svc.send_club_request_rejected(
            user.email, user.name, req.name, req.slug, req.admin_note, lang=lang
        )
    except Exception:
        _log.exception("tenant_request_mail_failed request_id=%s", req.id)
        return False


def _pending(req_id: int) -> TenantRequest:
    # Locked, so two admins deciding at once cannot both win.
    req = db.session.scalar(
        select(TenantRequest).where(TenantRequest.id == req_id).with_for_update()
    )
    if req is None:
        raise RequestDecisionError(404, "NOT_FOUND", "Tenant request not found")
    if req.status != "pending":
        raise RequestDecisionError(409, "CONFLICT", f"Request is already {req.status}")
    return req


def approve(
    req_id: int, reviewer_id, ip: str | None = None, via: str = ""
) -> tuple[TenantRequest, Tenant, bool]:
    """Set up the club and mark the request approved.  Commits.

    Returns ``(request, club, requester mailed)``.
    """
    from hubra.core.tenant.service import TenantProvisioningError, TenantService

    req = _pending(req_id)
    try:
        tenant = TenantService.provision_tenant(
            name=req.name,
            slug=req.slug,
            plan=req.plan,
            admin_email=None,
            admin_password=None,
            admin_user_id=req.user_id,
        )
    except TenantProvisioningError as exc:
        db.session.rollback()
        raise RequestDecisionError(422, "PROVISION_FAILED", str(exc)) from None

    req.status = "approved"
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    extra = {"via": via} if via else {}
    audit("approve", req, reviewer_id, ip, tenantId=tenant.id, **extra)
    db.session.commit()
    return req, tenant, notify_requester(req)


def reject(
    req_id: int, reviewer_id, note: str | None, ip: str | None = None, via: str = ""
) -> tuple[TenantRequest, bool]:
    """Mark the request rejected with *note* for the requester.  Commits."""
    req = _pending(req_id)
    req.status = "rejected"
    req.admin_note = (note or "").strip()[:2000] or None
    req.reviewed_by = int(reviewer_id) if reviewer_id else None
    extra = {"via": via} if via else {}
    audit("reject", req, reviewer_id, ip, note=req.admin_note, **extra)
    db.session.commit()
    return req, notify_requester(req)
