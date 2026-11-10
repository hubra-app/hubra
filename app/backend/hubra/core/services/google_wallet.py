"""The member badge in Google Wallet.

Hubra is the one issuer for every club: one Google Wallet issuer account,
one generic pass class, and one pass (a "generic object") per person. The
pass shows the person's name, their badge number as text and QR code
(``users.badge_code``, see ``services.member_badge``) and the names of their
clubs.

Setup (platform settings ``wallet.google.*``, manage › Platform › Google
Wallet): the issuer id from the Google Pay & Wallet Console, the id of the
generic class created there, and the JSON key of a Google Cloud service
account that has the Developer role on the issuer account. Without them the
"Add to Google Wallet" button is not shown and nothing here talks to Google.

How a pass gets to a phone: ``save_url`` writes the person's pass to
Google (insert, or patch when it's already there) and returns the
``pay.google.com/gp/v/save/<JWT>`` link. The JWT carries only the object's
id, so the link stays below the 1800 characters a browser link may have.

Keeping it current: a pass can't be deleted, only changed. ``queue_sync``
(after a member joins or leaves a club, a name change, an account deletion)
and the nightly ``refresh_all`` patch the pass when what it shows changed
(``users.google_wallet_hash``). A disabled or deleted account's pass is set
to INACTIVE; it moves to the expired passes on the phone.

Docs: https://developers.google.com/wallet/generic
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import jwt
from flask import current_app
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.user import User

_log = logging.getLogger(__name__)

API = "https://walletobjects.googleapis.com/walletobjects/v1"
SAVE_URL = "https://pay.google.com/gp/v/save/"
SCOPE = "https://www.googleapis.com/auth/wallet_object.issuer"
TOKEN_URI = "https://oauth2.googleapis.com/token"
TIMEOUT = 10  # seconds; Google recommends 10 (no SLA)
BACKGROUND = "#7441e0"  # Hubra violet


class WalletError(Exception):
    """Google refused a call, or Wallet is not set up."""


@dataclass(frozen=True)
class Config:
    issuer_id: str
    class_suffix: str
    client_email: str
    private_key: str
    token_uri: str
    logo_url: str

    @property
    def class_id(self) -> str:
        return f"{self.issuer_id}.{self.class_suffix}"


def parse_service_account(raw: str) -> dict | None:
    """The fields of a service account JSON key, or None when it isn't one."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("client_email") or "PRIVATE KEY" not in str(data.get("private_key")):
        return None
    return data


def config() -> Config | None:
    """The Wallet setup, or None while any part of it is missing."""
    from hubra.core.services import platform_settings

    try:
        issuer = platform_settings.get("wallet.google.issuer_id").strip()
        suffix = platform_settings.get("wallet.google.class_id").strip()
        key = platform_settings.get("wallet.google.service_account").strip()
        logo = platform_settings.get("wallet.google.logo_url").strip()
    except Exception:  # noqa: BLE001 - no database yet: Wallet is just off
        _log.debug("wallet settings not readable", exc_info=True)
        return None
    account = parse_service_account(key) if key else None
    if not (issuer and suffix and account):
        return None
    # The console shows the class as "<issuer>.<suffix>"; take either.
    suffix = suffix.removeprefix(f"{issuer}.")
    return Config(
        issuer_id=issuer,
        class_suffix=suffix,
        client_email=account["client_email"],
        private_key=account["private_key"],
        token_uri=account.get("token_uri") or TOKEN_URI,
        logo_url=logo,
    )


def enabled() -> bool:
    return config() is not None


# ── Talking to Google ────────────────────────────────────────────────────────

_TOKEN_LOCK = threading.Lock()
_TOKENS: dict[str, tuple[str, float]] = {}


def _access_token(cfg: Config) -> str:
    """An OAuth access token for the service account (cached until shortly
    before it runs out)."""
    with _TOKEN_LOCK:
        cached = _TOKENS.get(cfg.client_email)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": cfg.client_email,
            "scope": SCOPE,
            "aud": cfg.token_uri,
            "iat": now,
            "exp": now + 3600,
        },
        cfg.private_key,
        algorithm="RS256",
    )
    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode()
    status, data = _http("POST", cfg.token_uri, body, "application/x-www-form-urlencoded")
    if status != 200 or not data.get("access_token"):
        raise WalletError(f"Google sign-in for the Wallet API failed ({status})")
    token = data["access_token"]
    with _TOKEN_LOCK:
        _TOKENS[cfg.client_email] = (token, now + int(data.get("expires_in") or 3600))
    return token


def _http(method: str, url: str, body: bytes | None, ctype: str, token: str | None = None):
    """One HTTP call. Returns (status, parsed JSON body or {})."""
    req = urllib.request.Request(url, data=body, method=method)  # noqa: S310 - fixed https URLs
    req.add_header("Content-Type", ctype)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as err:
        raw = err.read() or b""
        status = err.code
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise WalletError(f"Google Wallet not reachable: {err}") from err
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    return status, data if isinstance(data, dict) else {}


def _api(cfg: Config, method: str, path: str, payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    return _http(method, f"{API}{path}", body, "application/json", _access_token(cfg))


def _upsert(cfg: Config, obj: dict) -> None:
    """Insert the pass, or patch it when Google has it already."""
    status, data = _api(cfg, "POST", "/genericObject", obj)
    if status == 409:
        oid = urllib.parse.quote(obj["id"], safe="")
        status, data = _api(cfg, "PATCH", f"/genericObject/{oid}", obj)
    if status >= 300:
        message = (data.get("error") or {}).get("message") if data else None
        raise WalletError(f"Google Wallet refused the pass ({status}): {message or 'no details'}")


# ── The pass ─────────────────────────────────────────────────────────────────


def _text(value: str, lang: str) -> dict:
    return {"defaultValue": {"language": lang, "value": value}}


def _object_id(cfg: Config, user: User) -> str:
    # Badge numbers are A-Z, 0-9 and "-", which object ids allow.
    return user.google_wallet_object or f"{cfg.issuer_id}.{user.badge_code}"


def pass_object(cfg: Config, user: User) -> dict:
    """The generic object Google stores for *user*."""
    from hubra.core.services import member_badge

    english = (user.language or "").lower().startswith("en")
    lang = "en" if english else "de"
    code = member_badge.ensure_code(user)
    oid = _object_id(cfg, user)
    if user.is_disabled:
        # A disabled or deleted account: no name or clubs on the pass any more.
        return {"id": oid, "classId": cfg.class_id, "state": "INACTIVE"}

    clubs = sorted(
        {m["club"]["name"] for m in member_badge.memberships(user) if m["club"]["name"]},
        key=str.casefold,
    )
    if clubs:
        body = "\n".join(clubs)
    else:
        body = "Not in a club yet" if english else "Noch in keinem Verein"
    obj = {
        "id": oid,
        "classId": cfg.class_id,
        "state": "ACTIVE",
        "cardTitle": _text("Hubra", lang),
        "subheader": _text("Member badge" if english else "Mitgliederausweis", lang),
        "header": _text(user.name or code, lang),
        "hexBackgroundColor": BACKGROUND,
        "barcode": {"type": "QR_CODE", "value": code, "alternateText": code},
        "textModulesData": [
            {"id": "clubs", "header": "Clubs" if english else "Vereine", "body": body}
        ],
    }
    if cfg.logo_url:
        obj["logo"] = {
            "sourceUri": {"uri": cfg.logo_url},
            "contentDescription": _text("Hubra", lang),
        }
    return obj


def _hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def save_url(user: User) -> str:
    """Write the person's pass to Google and return the "save to Google
    Wallet" link. Commits (the pass's id and state are kept on the user)."""
    cfg = config()
    if cfg is None:
        raise WalletError("Google Wallet is not set up")
    obj = pass_object(cfg, user)
    _upsert(cfg, obj)
    user.google_wallet_object = obj["id"]
    user.google_wallet_hash = _hash(obj)
    db.session.commit()
    token = jwt.encode(
        {
            "iss": cfg.client_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": _origins(),
            "payload": {"genericObjects": [{"id": obj["id"], "classId": cfg.class_id}]},
        },
        cfg.private_key,
        algorithm="RS256",
    )
    return SAVE_URL + token


def _origins() -> list[str]:
    base = (current_app.config.get("SSO_BASE_URL") or "").strip()
    host = urllib.parse.urlsplit(base).netloc if base else ""
    return [host] if host else []


def sync(user_id: int) -> bool:
    """Patch the person's pass when what it shows changed. Returns True when
    Google was called."""
    cfg = config()
    if cfg is None:
        return False
    user = db.session.get(User, user_id)
    if user is None or not user.google_wallet_object:
        return False
    obj = pass_object(cfg, user)
    digest = _hash(obj)
    if digest == user.google_wallet_hash:
        return False
    _upsert(cfg, obj)
    user.google_wallet_hash = digest
    db.session.commit()
    return True


def queue_sync(user_id: int | None) -> None:
    """Update the person's pass after the current transaction commits, when
    they have one."""
    if not user_id:
        return
    try:
        has_pass = db.session.scalar(
            select(User.google_wallet_object).where(User.id == user_id)
        )
    except Exception:  # noqa: BLE001 - never fail the caller over Wallet
        _log.debug("wallet pass lookup failed", exc_info=True)
        return
    if not has_pass or not enabled():
        return
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.wallet_tasks import sync_google_wallet_pass

    delay_after_commit(sync_google_wallet_pass, user_id)


def refresh_all() -> int:
    """Every pass whose content changed (a club renamed, a missed event).
    Returns how many were patched."""
    if not enabled():
        return 0
    ids = db.session.scalars(
        select(User.id).where(User.google_wallet_object.is_not(None))
    ).all()
    done = 0
    for uid in ids:
        try:
            done += bool(sync(uid))
        except WalletError:
            db.session.rollback()
            _log.warning("Google Wallet pass of user %s not updated", uid, exc_info=True)
    return done
