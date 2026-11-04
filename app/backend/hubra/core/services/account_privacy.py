"""A person's own data requests on the support site (support.hubra.club):
download everything the account holds, and delete the account.

Only the account lives here: the login, profile, sign-ins, devices, passkeys,
linked apps, API tokens and the person's own support cases.  What a club
keeps about its members (member record, invoices, attendance) belongs to the
club; the person asks the club for that, and leaves the club first.

Deleting does not remove the ``users`` row: support cases, audit entries and
archived member records in clubs point at it.  It is anonymised instead (no
name, address, phone or avatar; a login address that can never sign in) and
everything that lets someone sign in is removed.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from hubra.core.extensions import db
from hubra.core.models.user import User

# Columns that never leave the server, also not to their owner: secrets,
# hashes and the keys of push subscriptions.
_SECRET_PARTS = (
    "password",
    "hash",
    "secret",
    "token",
    "recovery",
    "credential",
    "public_key",
    "sign_count",
    "p256dh",
    "auth_key",
    "endpoint",
    "keys",
)

DELETED_DOMAIN = "deleted.invalid"


class PrivacyError(Exception):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _value(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _value(x) for k, x in v.items()}
    return str(v)


def _row(obj, skip: tuple[str, ...] = ()) -> dict:
    out = {}
    for col in obj.__table__.columns:
        name = col.name
        if name in skip or any(part in name for part in _SECRET_PARTS):
            continue
        out[name] = _value(getattr(obj, col.key, None))
    return out


def _rows(model, user_id: int, column: str = "user_id") -> list[dict]:
    items = db.session.scalars(
        select(model).where(getattr(model, column) == user_id)
    ).all()
    return [_row(i, skip=(column,)) for i in items]


def _models():
    from hubra.core.models.account_session import AccountSession
    from hubra.core.models.api_token import ApiToken
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.models.known_device import KnownDevice
    from hubra.core.models.passkey import Passkey
    from hubra.core.models.push_subscription import PushSubscription

    return AccountSession, ApiToken, ExternalAccount, KnownDevice, Passkey, PushSubscription


def export(user: User) -> dict:
    """Everything the account holds, as one JSON document."""
    from hubra.core.services import support
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.tenant_request import TenantRequest
    from hubra.core.models.user_tenant import UserTenant

    AccountSession, ApiToken, ExternalAccount, KnownDevice, Passkey, PushSubscription = _models()

    clubs = []
    for link, tenant in db.session.execute(
        select(UserTenant, Tenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == user.id)
    ).all():
        clubs.append(
            {
                "name": tenant.name,
                "slug": tenant.slug,
                "status": link.status,
                "owner": link.is_owner,
                "since": _value(link.created_at),
            }
        )

    cases = []
    for case in support.mine(user.id):
        full = support.own_case(user.id, case["id"])
        case["comments"] = support.comments_for(full, staff=False) if full else []
        case.pop("fingerprint", None)
        cases.append(case)

    return {
        "exportedAt": _value(datetime.now(timezone.utc)),
        "about": (
            "Your Hubra account. What a club keeps about you as a member "
            "(member record, invoices, attendance) is the club's: ask the club."
        ),
        "account": _row(user),
        "clubs": clubs,
        "signIns": _rows(AccountSession, user.id),
        "knownDevices": _rows(KnownDevice, user.id),
        "passkeys": _rows(Passkey, user.id),
        "pushSubscriptions": len(_rows(PushSubscription, user.id)),
        "linkedAccounts": _rows(ExternalAccount, user.id),
        "apiTokens": _rows(ApiToken, user.id),
        "clubRequests": _rows(TenantRequest, user.id),
        "supportCases": cases,
    }


def blockers(user: User) -> list[dict]:
    """What has to happen before the account can go."""
    from hubra.core.models.global_role import UserGlobalRole
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user_tenant import UserTenant

    out: list[dict] = []
    for link, tenant in db.session.execute(
        select(UserTenant, Tenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == user.id)
    ).all():
        out.append(
            {
                "kind": "club_owner" if link.is_owner else "club",
                "name": tenant.name,
                "slug": tenant.slug,
            }
        )
    staff = user.is_superadmin or db.session.scalar(
        select(UserGlobalRole.id).where(UserGlobalRole.user_id == user.id).limit(1)
    )
    if staff:
        out.append({"kind": "platform", "name": "Hubra", "slug": None})
    return out


def delete_account(user: User, password: str) -> None:
    """Anonymise the account and remove every way to sign in with it."""
    if not user.check_password(password or ""):
        raise PrivacyError("Current password is incorrect", "INVALID_PASSWORD")
    if blockers(user):
        raise PrivacyError(
            "Leave your clubs and hand over platform roles first",
            "ACCOUNT_IN_USE",
            409,
        )
    from hubra.core.models.email_verification import EmailVerificationToken
    from hubra.core.models.password_reset import PasswordResetToken
    from hubra.core.models.tenant import GlobalAuditEntry

    models = _models() + (EmailVerificationToken, PasswordResetToken)
    for model in models:
        db.session.execute(delete(model).where(model.user_id == user.id))

    user.email = f"deleted-{user.id}@{DELETED_DOMAIN}"
    user.first_name = "Gelöschtes Konto"
    user.last_name = ""
    user.set_password(secrets.token_urlsafe(48))
    user.is_disabled = True
    user.private_email_verified = False
    user.must_change_password = False
    for field in (
        "avatar",
        "profile_note",
        "phone",
        "mobile",
        "birthday",
        "address_street",
        "address_house_no",
        "address_postal_code",
        "address_city",
        "nav_prefs",
        "platform_alerts",
        "totp_secret",
        "totp_pending_secret",
        "totp_enabled_at",
        "totp_last_step",
        "recovery_codes",
        "last_seen",
    ):
        if hasattr(user, field):
            setattr(user, field, None)
    user.end_sessions()
    db.session.add(
        GlobalAuditEntry(
            actor_id=user.id,
            action="account_deleted",
            target_type="User",
            target_id=str(user.id),
            details={"by": "self"},
        )
    )
