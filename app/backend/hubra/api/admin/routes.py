"""Admin blueprint — tenant-scoped admin operations (domains, club settings).

Routes live at ``/api/v1/admin/*`` and are tenant-scoped (require a resolved
tenant via the middleware). All routes require ``@require_admin`` (tenant
admin role).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
            created = created.replace(tzinfo=UTC)
        stale = datetime.now(UTC) - created > PENDING_CLAIM_HOLD
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


def _check_mfa_rule(tenant, validated: dict) -> None:
    """Whoever turns "two-factor required" on has it, so they don't lock
    themselves out of the club they are setting up."""
    from hubra.api.auth import mfa
    from hubra.api.auth.helpers import get_current_user_id
    from hubra.core.errors import raise_error
    from hubra.core.models.user import User

    scope = validated.get("mfa_required")
    if scope in (None, "off") or scope == mfa.club_scope(tenant):
        return
    user = db.session.get(User, get_current_user_id())
    if user is None or not mfa.enabled(user):
        raise_error(
            400,
            "MFA_SETUP_FIRST",
            "Turn on two-factor sign-in for your own account first",
        )


def _mfa_overview(tenant) -> dict:
    """How many members still sign in without two-factor, for each scope."""
    from hubra.api.auth import mfa
    from hubra.api.permissions import held_roles
    from hubra.core.models.member import Member
    from hubra.core.models.passkey import Passkey

    members = db.session.scalars(
        select(Member).where(Member.archived_at.is_(None), Member.user_id.is_not(None))
    ).all()
    with_passkey = set(db.session.scalars(select(Passkey.user_id).distinct()))
    missing = {"admins": 0, "all": 0}
    for m in members:
        if m.user is None or mfa.totp_enabled(m.user) or m.user_id in with_passkey:
            continue
        missing["all"] += 1
        if any(r.is_admin or r.is_owner for r in held_roles(m)):
            missing["admins"] += 1
    return {"membersWithout": missing["all"], "adminsWithout": missing["admins"]}


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
    return jsonify({"settings": branding, "mfa": _mfa_overview(tenant)}), 200


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

    _check_mfa_rule(tenant, validated)

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


# ── Club backup key ─────────────────────────────────────────────────────────
#
# A club may hold its own age key pair: the public key lives on the tenant
# (``tenants.backup_public_key``) and every new backup of the club is
# encrypted to it as well as to the platform key, so the club can open its
# own backups.  The private key is made in the browser and never sent here.
# Platform admins can still set the key in manage › Encryption.


def _backup_key_state(tenant) -> dict:
    from hubra.core.models.backup import BackupRecord
    from hubra.core.services import backup_crypto

    meta = dict((tenant.settings or {}).get("backup_key") or {})
    keys = backup_crypto.split_keys(tenant.backup_public_key)
    # A key set from manage or the CLI has no note here; don't show a stale one.
    if meta.get("key") != tenant.backup_public_key:
        meta = {}
    latest = None
    if keys:
        query = select(BackupRecord).where(
            BackupRecord.tenant_id == tenant.id,
            BackupRecord.scope == "club",
            BackupRecord.status == "completed",
            BackupRecord.s3_key.like(f"%{backup_crypto.AGE_SUFFIX}"),
        )
        set_at = meta.get("set_at")
        if set_at:
            query = query.where(
                BackupRecord.created_at >= datetime.fromisoformat(set_at)
            )
        record = db.session.scalar(
            query.order_by(BackupRecord.created_at.desc()).limit(1)
        )
        latest = record.created_at.isoformat() if record else None
    return {
        "public_key": tenant.backup_public_key,
        "set_at": meta.get("set_at"),
        "set_by": meta.get("set_by"),
        # Only age (public-key) backups use club keys; a server still on the
        # older passphrase backups stores the key for later.
        "backups_use_key": backup_crypto.mode() == "age",
        # Only the club's key opens its backups: Hubra cannot restore them.
        "club_only": backup_crypto.club_only(tenant),
        "last_backup_with_key": latest,
    }


@admin_bp.get("/backup-key")
@require_admin
def get_backup_key():
    """The club's own backup public key and whether backups use it."""
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400
    return jsonify(_backup_key_state(tenant)), 200


@admin_bp.put("/backup-key")
@require_admin
def set_backup_key():
    """Body ``{"public_key": "age1..."}``: the club's own backup key.

    Only the public key comes here; anything that looks like a private key
    is refused so it is never stored or logged by mistake.
    """
    from hubra.api.auth.helpers import get_current_member
    from hubra.api.utils import log_audit
    from hubra.core.services.backup_crypto import split_keys, valid_public_key

    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400
    raw = (request.get_json(silent=True) or {}).get("public_key")
    if not isinstance(raw, str) or not raw.strip():
        return jsonify(
            {"error": "VALIDATION_ERROR", "message": "A public key is required"}
        ), 422
    if "AGE-SECRET-KEY" in raw.upper():
        return jsonify(
            {
                "error": "PRIVATE_KEY_SENT",
                "message": "That is the private key. Keep it to yourself and "
                "send only the public key (age1...).",
            }
        ), 422
    keys = split_keys(raw)
    if len(keys) != 1 or not valid_public_key(keys[0]):
        return jsonify(
            {"error": "VALIDATION_ERROR", "message": "Not an age public key (age1...)"}
        ), 422

    try:
        actor = get_current_member()
    except ApiError:  # a platform admin without a seat in the club
        actor = None
    settings = dict(tenant.settings or {})
    settings["backup_key"] = {
        "key": keys[0],
        "set_at": datetime.now(UTC).isoformat(),
        "set_by": f"{actor.first_name} {actor.last_name}".strip() if actor else None,
    }
    tenant.settings = settings
    tenant.backup_public_key = keys[0]
    log_audit(
        actor.id if actor else None,
        "set_backup_key",
        "Tenant",
        tenant.id,
        keys[0][:16] + "…",
    )
    db.session.commit()
    return jsonify(_backup_key_state(tenant)), 200


@admin_bp.delete("/backup-key")
@require_admin
def remove_backup_key():
    """Stop encrypting new backups to the club's key.  Backups made before
    still open with it, so the club should keep the private key."""
    from hubra.api.auth.helpers import get_current_member
    from hubra.api.utils import log_audit

    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400
    try:
        actor_id = get_current_member().id
    except ApiError:
        actor_id = None
    tenant.backup_public_key = None
    settings = dict(tenant.settings or {})
    settings.pop("backup_key", None)
    settings.pop("backup_club_only", None)
    tenant.settings = settings
    log_audit(actor_id, "remove_backup_key", "Tenant", tenant.id, None)
    db.session.commit()
    return jsonify(_backup_key_state(tenant)), 200


@admin_bp.patch("/backup-key")
@require_admin
def update_backup_key_options():
    """Body ``{"club_only": bool}``: whether only the club's own key opens
    its new backups.  Turning it on needs ``"confirm": "<club slug>"``,
    because Hubra can then no longer restore those backups."""
    from hubra.api.auth.helpers import get_current_member
    from hubra.api.utils import log_audit
    from hubra.core.services import backup_crypto

    tenant = current_tenant()
    if tenant is None:
        return jsonify({"error": "NO_TENANT", "message": "No tenant context"}), 400
    data = request.get_json(silent=True) or {}
    club_only = data.get("club_only")
    if not isinstance(club_only, bool):
        return jsonify(
            {"error": "VALIDATION_ERROR", "message": "club_only must be true or false"}
        ), 422
    if club_only:
        if not backup_crypto.split_keys(tenant.backup_public_key):
            return jsonify(
                {
                    "error": "NO_BACKUP_KEY",
                    "message": "Set up the club's backup key first",
                }
            ), 422
        if backup_crypto.mode() != "age":
            return jsonify(
                {
                    "error": "BACKUP_KEYS_UNSUPPORTED",
                    "message": "Backups on this server do not use public keys yet",
                }
            ), 422
        if data.get("confirm") != tenant.slug:
            return jsonify(
                {
                    "error": "CONFIRMATION_REQUIRED",
                    "message": "Type the club's short name to confirm",
                }
            ), 422
    try:
        actor_id = get_current_member().id
    except ApiError:
        actor_id = None
    settings = dict(tenant.settings or {})
    if club_only:
        settings["backup_club_only"] = True
    else:
        settings.pop("backup_club_only", None)
    tenant.settings = settings
    log_audit(
        actor_id,
        "backup_key_club_only_on" if club_only else "backup_key_club_only_off",
        "Tenant",
        tenant.id,
        None,
    )
    db.session.commit()
    return jsonify(_backup_key_state(tenant)), 200
