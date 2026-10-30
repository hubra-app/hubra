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
    verification_record_name,
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
    domain = Domain(
        tenant_id=tenant.id,
        domain=domain_name,
        verification_token=token,
        verification_status="pending",
        # Only a verified domain can be the club's primary one.
        is_primary=False,
    )
    db.session.add(domain)
    db.session.flush()
    _audit_domain("add_domain", domain)
    db.session.commit()

    return (
        jsonify(
            {
                "domain": _domain_to_dict(domain),
                "txt_record": _txt_record(domain),
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

    from hubra.core.tasks.domain_tasks import check_domain

    result = check_domain(domain)
    if result["verified"]:
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
            .where(Domain.tenant_id == tenant.id, Domain.verified.is_(True))
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
    branding = dict(settings.get("branding", {}))
    # The form shows the club's name even before anyone saved one here.
    if not branding.get("club_name"):
        branding["club_name"] = tenant.name
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
    # One name everywhere: the club list, invites and the manager portal
    # read tenant.name, so renaming the club here renames it there too.
    new_name = (validated.get("club_name") or "").strip()
    if new_name:
        tenant.name = new_name

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


# ── Bank details for QR invoices ─────────────────────────────────────────────

# (field in the API, setting key, label)
_BANK_FIELDS = (
    ("iban", "Club.Banking.Iban", "IBAN / QR-IBAN"),
    ("street", "Club.Banking.Street", "Street"),
    ("houseNo", "Club.Banking.HouseNo", "House number"),
    ("postalCode", "Club.Banking.PostalCode", "Postal code"),
    ("city", "Club.Banking.City", "City"),
    ("country", "Club.Banking.Country", "Country"),
)


def _bank_settings() -> dict:
    from hubra.api.settings.services import SettingService

    data = {f: SettingService.get(key, "") or "" for f, key, _ in _BANK_FIELDS}
    data["country"] = data["country"] or "CH"
    iban = data["iban"].replace(" ", "").upper()
    # IID 30-31 marks a QR-IBAN: invoices then carry a QR reference that the
    # bank import matches payments by.
    data["isQrIban"] = len(iban) >= 6 and iban[4:6] in ("30", "31")
    data["complete"] = bool(data["iban"] and data["postalCode"] and data["city"])
    return data


def _iban_error(value: str) -> str | None:
    """None for a valid Swiss or Liechtenstein IBAN (what a QR bill takes)."""
    import re

    v = value.replace(" ", "").upper()
    if not re.match(r"^(CH|LI)\d{7}[0-9A-Z]{12}$", v):
        return "IBAN must be a Swiss or Liechtenstein IBAN (CH or LI, 21 characters)"
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - 55) for ch in v[4:] + v[:4])
    if int(numeric) % 97 != 1:
        return "IBAN checksum is wrong"
    return None


@admin_bp.get("/bank-settings")
@require_admin
def get_bank_settings():
    """The account and address the club's QR invoices are paid to."""
    return jsonify(_bank_settings()), 200


@admin_bp.put("/bank-settings")
@require_admin
def update_bank_settings():
    """Save the club's IBAN and creditor address (Settings > Verein)."""
    from hubra.api.settings.services import SettingService

    body = request.get_json(silent=True) or {}
    values = {}
    for field, _key, _label in _BANK_FIELDS:
        raw = body.get(field, "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            raise ApiError(400, "VALIDATION_ERROR", f"{field} must be text")
        values[field] = raw.strip()[:70]
    if values["iban"]:
        values["iban"] = values["iban"].replace(" ", "").upper()
        error = _iban_error(values["iban"])
        if error:
            raise ApiError(400, "VALIDATION_ERROR", error)
    values["country"] = (values["country"] or "CH").upper()
    if len(values["country"]) != 2 or not values["country"].isalpha():
        raise ApiError(400, "VALIDATION_ERROR", "country must be a 2-letter code")

    for field, key, label in _BANK_FIELDS:
        SettingService.upsert(
            key, {"value": values[field], "namespace": "club", "label": label}
        )
    tenant = current_tenant()
    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant.id if tenant else None,
            action="bank_settings.update",
            target_type="Tenant",
            target_id=str(tenant.id) if tenant else "",
            details={"isQrIban": _bank_settings()["isQrIban"]},
        )
    )
    db.session.commit()
    return jsonify(_bank_settings()), 200


# ── Helpers ─────────────────────────────────────────────────────────────────


def _txt_record(domain: Domain) -> dict:
    name = verification_record_name(domain.domain)
    value = f"{_VERIFICATION_PREFIX}{domain.verification_token}"
    return {
        "name": name,
        "value": value,
        "instructions": f"Add a TXT record named '{name}' with value '{value}' to your DNS.",
    }


def _domain_to_dict(domain: Domain) -> dict:
    return {
        "id": domain.id,
        "domain": domain.domain,
        "verified": domain.verified,
        "verification_token": domain.verification_token,
        "verification_status": domain.verification_status,
        "is_primary": domain.is_primary,
        "verified_at": domain.verified_at.isoformat() if domain.verified_at else None,
        "last_checked_at": domain.last_checked_at.isoformat()
        if domain.last_checked_at
        else None,
        "txt_record": _txt_record(domain) if domain.verification_token else None,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }
