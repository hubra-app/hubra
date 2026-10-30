"""Translation suggestions: clubs propose, platform admins decide."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from hubra.api.i18n.services import upsert_translation
from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant
from hubra.core.models.translation import Translation
from hubra.core.models.translation_request import TranslationRequest

STATUSES = ("pending", "accepted", "rejected")


class RequestError(ValueError):
    pass


def current_text(locale: str, key: str) -> str | None:
    row = db.session.scalar(
        select(Translation).where(Translation.locale == locale, Translation.key == key)  # type: ignore[arg-type]
    )
    return row.value if row is not None and row.value else None


def submit(
    tenant_id: int, user_id: int | None, locale: str, key: str, value: str, note: str | None
) -> TranslationRequest:
    key, value = key.strip(), value.strip()
    if not key or len(key) > 255:
        raise RequestError("key is required")
    if not value:
        raise RequestError("The suggested text is empty")
    current = current_text(locale, key)
    if current == value:
        raise RequestError("The suggested text is the current text")
    req = TranslationRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        locale=locale,
        key=key,
        current_value=current,
        proposed_value=value,
        note=(note or "").strip() or None,
    )
    db.session.add(req)
    db.session.flush()
    return req


def for_club(tenant_id: int) -> list[TranslationRequest]:
    stmt = (
        select(TranslationRequest)
        .where(TranslationRequest.tenant_id == tenant_id)  # type: ignore[arg-type]
        .order_by(TranslationRequest.created_at.desc(), TranslationRequest.id.desc())
    )
    return list(db.session.scalars(stmt).all())


def listing(status: str | None) -> list[dict]:
    stmt = select(TranslationRequest, Tenant.name).outerjoin(
        Tenant, Tenant.id == TranslationRequest.tenant_id
    )
    if status:
        stmt = stmt.where(TranslationRequest.status == status)  # type: ignore[arg-type]
    stmt = stmt.order_by(TranslationRequest.created_at.desc(), TranslationRequest.id.desc())
    out = []
    for req, name in db.session.execute(stmt).all():
        d = req.to_dict(name)
        # What the text is now, which may have changed since the suggestion.
        d["liveValue"] = current_text(req.locale, req.key)
        out.append(d)
    return out


def decide(
    req: TranslationRequest,
    accept: bool,
    user_id: int | None,
    value: str | None = None,
    note: str | None = None,
) -> TranslationRequest:
    if req.status != "pending":
        raise RequestError("This suggestion was already decided")
    if accept:
        text = (value if value is not None else req.proposed_value).strip()
        if not text:
            raise RequestError("The suggested text is empty")
        upsert_translation(locale=req.locale, key=req.key, value=text, updated_by_id=None)
        req.proposed_value = text
    req.status = "accepted" if accept else "rejected"
    req.decided_by = user_id
    req.decided_at = datetime.now(timezone.utc)
    req.decision_note = (note or "").strip() or None
    return req
