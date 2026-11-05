"""Sign in with Hubra: OpenID Connect on top of the OAuth server
(docs/oidc.md, hubra/core/auth/oauth.py).

An app that may ask for ``openid`` gets an ID token next to its tokens: a
JWT signed with the platform's RSA key (RS256, published at the JWKS
address) that says who signed in. ``profile``, ``email`` and, for a club's
own app, ``club`` add the person's name, address and membership. The same
claims come from the userinfo endpoint, always as they are *now*.

* ``sub`` is per app (pairwise): two apps can't match up a person by it.
* An app that only signs people in holds an ``identity`` sign-in: it reads
  nothing from Hubra, its access token only opens userinfo.
* A club's app signs in only that club's members (not archived, not
  blocked), checked at sign-in, on every refresh and on userinfo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, text

from hubra.core.extensions import db

OIDC_SCOPES = ("openid", "profile", "email", "club")
ID_TOKEN_TTL = timedelta(hours=1)
# How long an app's sign-in-only grant lasts; signing in again renews it.
IDENTITY_DAYS = 90
ALG = "RS256"
# The JWKS keeps the key before the newest, so tokens signed just before a
# rotation still check out.
MAX_KEYS = 2

_KEYS = "oauth.signing_keys"
_SALT = "oauth.subject_salt"
_LOCK_KEY = 0x6875627261696473  # "hubraids"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# ── Keys ────────────────────────────────────────────────────────────────────


def _lock() -> None:
    """Two processes making the first key at once must not each store one."""
    from hubra.core.services import platform_settings

    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
        platform_settings._forget(db.session())


def _new_key() -> dict:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    der = private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    return {
        "kid": _b64(hashlib.sha256(der).digest())[:16],
        "pem": pem,
        "created": _now().isoformat(),
    }


def _stored_keys() -> list[dict]:
    from hubra.core.services import platform_settings

    raw = platform_settings.get(_KEYS)
    try:
        keys = json.loads(raw) if raw else []
    except ValueError:
        keys = []
    return [k for k in keys if isinstance(k, dict) and k.get("kid") and k.get("pem")]


def signing_keys(create: bool = True) -> list[dict]:
    """The keys, newest first; with *create*, the first one is made and
    stored (flushed, not committed) when there is none."""
    from hubra.core.services import platform_settings

    keys = _stored_keys()
    if keys or not create:
        return keys
    _lock()
    keys = _stored_keys()
    if not keys:
        keys = [_new_key()]
        platform_settings.set_many({_KEYS: json.dumps(keys)})
    return keys


def rotate_keys() -> list[dict]:
    """A new signing key first; the one before stays in the JWKS."""
    from hubra.core.services import platform_settings

    _lock()
    keys = [_new_key(), *_stored_keys()][:MAX_KEYS]
    platform_settings.set_many({_KEYS: json.dumps(keys)})
    return keys


def _public_jwk(key: dict) -> dict:
    private = serialization.load_pem_private_key(key["pem"].encode("ascii"), password=None)
    numbers = private.public_key().public_numbers()

    def as_b64(n: int) -> str:
        return _b64(n.to_bytes((n.bit_length() + 7) // 8, "big"))

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": ALG,
        "kid": key["kid"],
        "n": as_b64(numbers.n),
        "e": as_b64(numbers.e),
    }


def jwks() -> dict:
    return {"keys": [_public_jwk(k) for k in signing_keys()]}


def keys_info() -> list[dict]:
    """For manage: which keys there are (never the private part)."""
    return [{"kid": k["kid"], "created": k.get("created")} for k in signing_keys(create=False)]


# ── Who signed in ───────────────────────────────────────────────────────────


def _salt() -> bytes:
    from hubra.core.services import platform_settings

    salt = platform_settings.get(_SALT)
    if not salt:
        _lock()
        salt = platform_settings.get(_SALT)
        if not salt:
            salt = secrets.token_urlsafe(32)
            platform_settings.set_many({_SALT: salt})
    return salt.encode("utf-8")


def subject(client_id: str, user_id: int) -> str:
    """The person's id for this app: stable, and different in every app."""
    digest = hmac.new(_salt(), f"{client_id}:{user_id}".encode(), hashlib.sha256).digest()
    return _b64(digest)[:32]


def club_member(tenant, user_id: int):
    """``(member, admin, groups)`` when *user_id* is an active member of
    *tenant* (not archived, not blocked), else None."""
    from hubra.core.models.group import Group, GroupMembership
    from hubra.core.models.member import Member
    from hubra.core.permissions import held_roles
    from hubra.core.tenant.context import in_club

    if tenant is None or tenant.status != "active":
        return None
    with in_club(tenant):
        member = db.session.scalar(select(Member).where(Member.user_id == user_id))
        if member is None or member.archived_at is not None or member.is_blocked:
            return None
        roles = held_roles(member)
        admin = any(r.is_owner or r.is_admin for r in roles)
        groups = sorted(
            db.session.scalars(
                select(Group.name)
                .join(GroupMembership, GroupMembership.group_id == Group.id)
                .where(GroupMembership.member_id == member.id)
            ).all()
        )
        info = {
            "member_id": member.id,
            "status": member.status,
            "username": member.club_username,
        }
    return info, admin, groups


def claims(user, scopes: list[str] | set[str], *, tenant=None) -> dict:
    """The claims *scopes* let an app see, as they are now."""
    out: dict = {}
    if "profile" in scopes:
        name = f"{user.first_name} {user.last_name}".strip()
        out.update(
            {
                "name": name or user.email,
                "given_name": user.first_name or None,
                "family_name": user.last_name or None,
                "locale": (user.language or "de").replace("_", "-"),
            }
        )
    if "email" in scopes:
        out["email"] = user.email
        out["email_verified"] = bool(user.private_email_verified)
    if "club" in scopes and tenant is not None:
        found = club_member(tenant, user.id)
        if found is not None:
            info, admin, groups = found
            out["hubra_club"] = {
                "slug": tenant.slug,
                "name": tenant.name,
                "member_status": info["status"],
                "admin": admin,
                "groups": groups,
            }
            if "profile" in scopes and info["username"]:
                out["preferred_username"] = info["username"]
    return {k: v for k, v in out.items() if v is not None}


def _at_hash(access_token: str) -> str:
    digest = hashlib.sha256(access_token.encode("ascii")).digest()
    return _b64(digest[: len(digest) // 2])


def id_token(
    *,
    client,
    user,
    scopes: list[str],
    access_token: str | None,
    nonce: str | None = None,
    auth_time: datetime | None = None,
    tenant=None,
) -> str:
    """A signed ID token for *user*, for *client*."""
    from hubra.core.auth import oauth

    now = _now()
    payload: dict = {
        "iss": oauth.issuer(),
        "sub": subject(client.client_id, user.id),
        "aud": client.client_id,
        "azp": client.client_id,
        "iat": int(now.timestamp()),
        "exp": int((now + ID_TOKEN_TTL).timestamp()),
    }
    if auth_time is not None:
        payload["auth_time"] = int(oauth._aware(auth_time).timestamp())
    if nonce:
        payload["nonce"] = nonce
    if access_token:
        payload["at_hash"] = _at_hash(access_token)
    payload.update(claims(user, scopes, tenant=tenant))
    key = signing_keys()[0]
    return jwt.encode(payload, key["pem"], algorithm=ALG, headers={"kid": key["kid"]})


# ── Metadata ────────────────────────────────────────────────────────────────

CLAIMS = (
    "sub",
    "iss",
    "aud",
    "exp",
    "iat",
    "auth_time",
    "nonce",
    "at_hash",
    "name",
    "given_name",
    "family_name",
    "locale",
    "preferred_username",
    "email",
    "email_verified",
    "hubra_club",
)


def discovery() -> dict:
    """``/.well-known/openid-configuration`` (OpenID Connect Discovery)."""
    from hubra.core.auth import oauth

    meta = oauth.server_metadata()
    base = oauth.issuer()
    meta.update(
        {
            "userinfo_endpoint": f"{base}/api/v1/global/oauth/userinfo",
            "jwks_uri": f"{base}/api/v1/global/oauth/jwks",
            "scopes_supported": [*OIDC_SCOPES, *oauth.SCOPES],
            "subject_types_supported": ["pairwise"],
            "id_token_signing_alg_values_supported": [ALG],
            "claims_supported": list(CLAIMS),
            "prompt_values_supported": ["none", "consent"],
            "claims_parameter_supported": False,
            "request_parameter_supported": False,
            "request_uri_parameter_supported": False,
            "service_documentation": "https://github.com/hubra-app/hubra/blob/main/docs/oidc.md",
        }
    )
    return meta


# ── userinfo ────────────────────────────────────────────────────────────────


def userinfo(raw: str | None) -> tuple[dict | None, str]:
    """``(claims, "")`` for a live access token of a sign-in that asked for
    ``openid``, else ``(None, error)`` with an RFC 6750 error code."""
    from hubra.core.auth import api_tokens, oauth
    from hubra.core.models.api_token import ApiToken
    from hubra.core.models.oauth import OAuthClient
    from hubra.core.models.user import User

    parsed = api_tokens.parse(raw or "")
    if parsed is None or not api_tokens.is_oauth(raw or ""):
        return None, "invalid_token"
    kind, public_id, secret = parsed
    row = db.session.scalar(select(ApiToken).where(ApiToken.public_id == public_id))
    if row is None or row.kind != kind or row.oauth_client_id is None:
        return None, "invalid_token"
    now = _now()
    if not oauth._matches(row.secret_hash, secret):
        if not oauth._matches(row.prev_secret_hash, secret):
            api_tokens._record_failure(row, now)
        return None, "invalid_token"
    access_until = oauth._aware(row.access_expires_at)
    if not api_tokens.is_active(row, now) or access_until is None or access_until <= now:
        return None, "invalid_token"
    scopes = (row.oauth_scope or "").split()
    if "openid" not in scopes:
        return None, "insufficient_scope"
    client = db.session.get(OAuthClient, row.oauth_client_id)
    user = db.session.get(User, row.user_id)
    cutoff = oauth._aware(user.tokens_valid_after) if user is not None else None
    if (
        client is None
        or client.disabled_at is not None
        or user is None
        or user.is_disabled
        or (cutoff is not None and oauth._aware(row.created_at) < cutoff)
    ):
        return None, "invalid_token"
    tenant = oauth._club_of(client)
    if client.tenant_id is not None and (tenant is None or club_member(tenant, user.id) is None):
        return None, "invalid_token"
    row.last_used_at = now
    row.use_count = (row.use_count or 0) + 1
    out = {"sub": subject(client.client_id, user.id)}
    out.update(claims(user, scopes, tenant=tenant))
    return out, ""
