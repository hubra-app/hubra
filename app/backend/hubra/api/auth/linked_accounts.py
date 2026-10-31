"""Linked accounts: /api/v1/account/linked-accounts (SSO account page).

A person links their own outside account (Discord) to their Hubra account.
Clubs never do this for them. Each club the person is in hears about it
(``account.linked`` / ``account.unlinked``) so, for example, the Discord bot
can give or take the person's roles.
"""

from __future__ import annotations

import secrets as _secrets

from flask import Blueprint, current_app, jsonify, make_response, redirect, request
from flask_jwt_extended import current_user, jwt_required, verify_jwt_in_request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from urllib.parse import urlencode

from hubra.api.permissions import refuse_during_impersonation
from hubra.core import identity
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.connected_app import ExternalAccount
from hubra.core.models.user import User

linked_accounts_bp = Blueprint("linked_accounts_bp", __name__)

_COOKIE = "hubra_link_account"
_MAX_AGE = 600


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="linked-accounts"
    )


def _user() -> User | None:
    if isinstance(current_user, User):
        return current_user
    return getattr(current_user, "user", None)


def _provider_or_404(code: str):
    found = identity.provider(code)
    if found is None:
        raise_error(404, "NOT_FOUND", f"Unknown account type '{code}'")
    return found


def _callback_url(code: str) -> str:
    base = current_app.config.get("API_PUBLIC_URL") or request.host_url
    return f"{base.rstrip('/')}/api/v1/account/linked-accounts/{code}/callback"


def _serialize(acc: ExternalAccount) -> dict:
    return {
        "provider": acc.provider,
        "externalId": acc.external_id,
        "username": acc.username,
        "linkedAt": acc.created_at.isoformat() if acc.created_at else None,
    }


def _announce(user_id: int, event: str, acc: ExternalAccount) -> None:
    """Tell each of the person's clubs (role sync and the like)."""
    from hubra.core.modules import emit
    from hubra.core.services import account as account_svc

    for _tenant, member in account_svc.memberships(user_id):
        emit(
            event,
            member_id=member.id,
            user_id=user_id,
            provider=acc.provider,
            external_id=acc.external_id,
        )


@linked_accounts_bp.get("/")
@jwt_required()
def list_linked():
    user = _user()
    if user is None:
        raise_error(401, "UNAUTHORIZED", "User not found")
    accounts = db.session.scalars(
        select(ExternalAccount).where(ExternalAccount.user_id == user.id)
    ).all()
    return jsonify(
        {
            "providers": [
                {"code": p.code, "name": p.name, "available": p.available()}
                for p in identity.PROVIDERS.values()
            ],
            "accounts": [_serialize(a) for a in accounts],
        }
    ), 200


@linked_accounts_bp.post("/<string:code>/start")
@jwt_required()
def start_link(code: str):
    refuse_during_impersonation()
    found = _provider_or_404(code)
    user = _user()
    if user is None:
        raise_error(401, "UNAUTHORIZED", "User not found")
    if not found.available():
        return api_error(
            "UNAVAILABLE", f"{found.name} isn't set up on this platform", 409
        )
    nonce = _secrets.token_urlsafe(24)
    state = _serializer().dumps({"u": user.id, "p": code, "n": nonce})
    response = make_response(
        jsonify({"url": found.authorize_url(state, _callback_url(code))}), 200
    )
    response.set_cookie(
        _COOKIE,
        nonce,
        max_age=_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("JWT_COOKIE_SECURE", False),
    )
    return response


def _back(**params):
    from hubra.core.services.email import _get_sso_base_url

    base = _get_sso_base_url()
    path = f"{base}/account/verknuepfungen" if base else "/account/verknuepfungen"
    response = make_response(redirect(f"{path}?{urlencode(params)}"))
    response.delete_cookie(_COOKIE)
    return response


@linked_accounts_bp.get("/<string:code>/callback")
def link_callback(code: str):
    found = identity.provider(code)
    if found is None:
        return _back(error="failed")
    try:
        data = _serializer().loads(request.args.get("state", ""), max_age=_MAX_AGE)
    except BadSignature:
        return _back(provider=code, error="expired")
    nonce = request.cookies.get(_COOKIE)
    if (
        data.get("p") != code
        or not nonce
        or not _secrets.compare_digest(str(data.get("n")), nonce)
    ):
        return _back(provider=code, error="expired")
    if request.args.get("error"):
        return _back(provider=code, error="cancelled")
    # The link must land on the account that started it, in this browser.
    try:
        verify_jwt_in_request()
    except Exception:
        return _back(provider=code, error="signin")
    user = _user()
    if user is None or user.id != data.get("u"):
        return _back(provider=code, error="signin")

    try:
        who = found.identify(request.args.get("code", ""), _callback_url(code))
    except identity.IdentityError as exc:
        current_app.logger.info("linking %s failed: %s", code, exc)
        return _back(provider=code, error="failed")

    other = db.session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.provider == code,
            ExternalAccount.external_id == who.external_id,
        )
    )
    if other is not None and other.user_id != user.id:
        return _back(provider=code, error="taken")
    acc = db.session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id, ExternalAccount.provider == code
        )
    )
    previous = None
    if acc is None:
        acc = ExternalAccount(user_id=user.id, provider=code)
        db.session.add(acc)
    elif acc.external_id != who.external_id:
        previous = ExternalAccount(
            user_id=user.id, provider=code, external_id=acc.external_id
        )
    acc.external_id = who.external_id
    acc.username = who.username
    db.session.commit()
    if previous is not None:
        _announce(user.id, "account.unlinked", previous)
    _announce(user.id, "account.linked", acc)
    db.session.commit()
    return _back(linked=code)


@linked_accounts_bp.delete("/<string:code>")
@jwt_required()
def unlink(code: str):
    refuse_during_impersonation()
    _provider_or_404(code)
    user = _user()
    if user is None:
        raise_error(401, "UNAUTHORIZED", "User not found")
    acc = db.session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id, ExternalAccount.provider == code
        )
    )
    if acc is None:
        raise_error(404, "NOT_FOUND", "Not linked")
    gone = ExternalAccount(user_id=user.id, provider=code, external_id=acc.external_id)
    db.session.delete(acc)
    db.session.commit()
    _announce(user.id, "account.unlinked", gone)
    db.session.commit()
    return jsonify({"ok": True}), 200


def linked_user_id(code: str, external_id: str) -> int | None:
    """The Hubra account an outside account belongs to, for providers."""
    return db.session.scalar(
        select(ExternalAccount.user_id).where(
            ExternalAccount.provider == code,
            ExternalAccount.external_id == str(external_id),
        )
    )
