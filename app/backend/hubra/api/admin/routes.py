"""Admin blueprint — tenant-scoped admin operations (domains, club settings).

Routes live at ``/api/v1/admin/*`` and are tenant-scoped (require a resolved
tenant via the middleware). All routes require ``@require_admin`` (tenant
admin role).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from sqlalchemy import select

from hubra.api.permissions import require_admin
from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.domain import Domain
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.schemas.club_settings import ClubSettingsSchema
from hubra.core.services.dns_verification import (
    _VERIFICATION_PREFIX,
    generate_verification_token,
    verify_domain,
)
from hubra.core.tenant.context import current_tenant

# How long a club's unproven claim on a domain keeps others from claiming it.
PENDING_CLAIM_HOLD = timedelta(hours=72)

admin_bp = Blueprint("admin_bp", __name__)


# ── Domain CRUD ─────────────────────────────────────────────────────────────


def _audit_domain(action: str, domain: Domain) -> None:
    from hubra.api.auth.helpers import get_current_member
    from hubra.api.utils import log_audit

    try:
        actor_id = get_current_member().id
    except ApiError:  # a platform admin without a seat in the club
        actor_id = None
    log_audit(actor_id, action, "Domain", domain.id, domain.domain)


@admin_bp.get("/domains")
@require_admin
def list_domains():
    """List all domains for the current tenant."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    domains = list(
        db.session.scalars(
            select(Domain)
            .where(Domain.tenant_id == tenant.id)
            .order_by(Domain.created_at)
        ).all()
    )
    return jsonify({"domains": [_domain_to_dict(d) for d in domains]}), 200


@admin_bp.post("/domains")
@require_admin
def add_domain():
    """Add a new domain with auto-generated verification token."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    data = request.get_json(silent=True) or {}
    domain_name = str(data.get("domain") or "").strip().lower()

    if not domain_name or "." not in domain_name:
        return jsonify(
            {"error": "VALIDATION_ERROR", "message": "A valid domain is required"}
        ), 422

    if len(domain_name) > 255:
        return jsonify(
            {"error": "VALIDATION_ERROR", "message": "Domain too long (max 255 chars)"}
        ), 422

    existing = db.session.scalar(select(Domain).where(Domain.domain == domain_name))
    if existing is not None:
        # A claim nobody proved is only held for a while: after that another
        # club may claim it, so no club can sit on someone else's domain.
        created = existing.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        stale = datetime.now(timezone.utc) - created > PENDING_CLAIM_HOLD
        if existing.verified or existing.tenant_id == tenant.id or not stale:
            return jsonify(
                {"error": "CONFLICT", "message": "Domain already registered"}
            ), 409
        db.session.delete(existing)
        db.session.flush()

    token = generate_verification_token()
    is_first = (
        db.session.scalar(
            select(db.func.count())
            .select_from(Domain)
            .where(Domain.tenant_id == tenant.id)
        )
        == 0
    )

    domain = Domain(
        tenant_id=tenant.id,
        domain=domain_name,
        verification_token=token,
        verification_status="pending",
        is_primary=is_first,
    )
    db.session.add(domain)
    db.session.flush()
    _audit_domain("add_domain", domain)
    db.session.commit()

    return (
        jsonify(
            {
                "domain": _domain_to_dict(domain),
                "txt_record": {
                    "name": domain_name,
                    "value": f"{_VERIFICATION_PREFIX}{token}",
                    "instructions": f"Add a TXT record with value '{_VERIFICATION_PREFIX}{token}' to your DNS configuration for {domain_name}.",
                },
            }
        ),
        201,
    )


@admin_bp.post("/domains/<int:domain_id>/verify")
@require_admin
def verify_domain_endpoint(domain_id: int):
    """Trigger DNS verification for a domain."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    domain = db.session.get(Domain, domain_id)
    if domain is None or domain.tenant_id != tenant.id:
        return jsonify({"error": "NOT_FOUND", "message": "Domain not found"}), 404

    if domain.verification_status == "verified":
        return jsonify(
            {"domain": _domain_to_dict(domain), "message": "Already verified"}
        ), 200

    if not domain.verification_token:
        return jsonify(
            {"error": "NO_TOKEN", "message": "No verification token for this domain"}
        ), 400

    result = verify_domain(domain.domain, domain.verification_token)

    if result["verified"]:
        from datetime import datetime, timezone

        domain.verified = True
        domain.verification_status = "verified"
        domain.verified_at = datetime.now(timezone.utc)
        _audit_domain("verify_domain", domain)
        db.session.commit()

    return jsonify(
        {
            "domain": _domain_to_dict(domain),
            "verified": result["verified"],
            "found_records": result.get("found_records", []),
            "error": result.get("error"),
        }
    ), 200 if result["verified"] else 202


@admin_bp.delete("/domains/<int:domain_id>")
@require_admin
def remove_domain(domain_id: int):
    """Remove a domain."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    domain = db.session.get(Domain, domain_id)
    if domain is None or domain.tenant_id != tenant.id:
        return jsonify({"error": "NOT_FOUND", "message": "Domain not found"}), 404

    was_primary = domain.is_primary
    _audit_domain("remove_domain", domain)
    db.session.delete(domain)
    db.session.flush()

    if was_primary:
        next_domain = db.session.scalar(
            select(Domain)
            .where(Domain.tenant_id == tenant.id)
            .order_by(Domain.created_at)
            .limit(1)
        )
        if next_domain is not None:
            next_domain.is_primary = True

    db.session.commit()
    return "", 204


@admin_bp.patch("/domains/<int:domain_id>/primary")
@require_admin
def set_primary_domain(domain_id: int):
    """Set a domain as the primary domain for the tenant."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    domain = db.session.get(Domain, domain_id)
    if domain is None or domain.tenant_id != tenant.id:
        return jsonify({"error": "NOT_FOUND", "message": "Domain not found"}), 404

    if not domain.verified:
        return jsonify(
            {
                "error": "DOMAIN_NOT_VERIFIED",
                "message": "Domain must be verified before setting as primary",
            }
        ), 422

    others = list(
        db.session.scalars(
            select(Domain).where(Domain.tenant_id == tenant.id, Domain.id != domain_id)
        ).all()
    )
    for d in others:
        d.is_primary = False
    domain.is_primary = True
    _audit_domain("set_primary_domain", domain)
    db.session.commit()

    return jsonify({"domain": _domain_to_dict(domain)}), 200


# ── Club settings (branding) ────────────────────────────────────────────────

_club_settings_schema = ClubSettingsSchema()


@admin_bp.get("/club-settings")
@require_admin
def get_club_settings():
    """Return the current tenant's branding settings."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    settings = dict(tenant.settings or {})
    branding = settings.get("branding", {})
    return jsonify({"settings": branding}), 200


@admin_bp.patch("/club-settings")
@require_admin
def update_club_settings():
    """Update the current tenant's branding settings.

    Merges provided fields into the existing ``Tenant.settings['branding']``
    dict. Only provided fields are updated; a field sent as null is removed.
    """
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400

    body = request.get_json(silent=True) or {}

    try:
        validated = _club_settings_schema.load(body)
    except ValidationError as exc:
        return jsonify({"error": "VALIDATION_ERROR", "message": str(exc.messages)}), 422

    settings = dict(tenant.settings or {})
    branding = dict(settings.get("branding", {}))
    for key, value in validated.items():
        # null clears a field, so a club can take its logo or colours away.
        if value is None:
            branding.pop(key, None)
        else:
            branding[key] = value
    settings["branding"] = branding
    tenant.settings = settings

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id,
            action="club_settings.update",
            target_type="Tenant",
            target_id=str(tenant.id),
            details={"fields": list(validated.keys())},
        )
    )
    db.session.commit()

    return jsonify({"settings": branding}), 200


# ── Helpers ─────────────────────────────────────────────────────────────────


def _domain_to_dict(domain: Domain) -> dict:
    return {
        "id": domain.id,
        "domain": domain.domain,
        "verified": domain.verified,
        "verification_token": domain.verification_token,
        "verification_status": domain.verification_status,
        "is_primary": domain.is_primary,
        "verified_at": domain.verified_at.isoformat() if domain.verified_at else None,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }
