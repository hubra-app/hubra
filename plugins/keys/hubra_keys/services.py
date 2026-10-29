"""Key service: CRUD plus issue, return, lost and found with a handover log."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member

from .models import KEY_KINDS, KEY_STATUSES, Key, KeyHandover

_EDITABLE = ("label", "number", "kind", "opens", "deposit_chf", "code_id", "notes")


def key_to_dict(key: Key, with_history: bool = False) -> dict:
    data = {
        "id": key.id,
        "label": key.label,
        "number": key.number,
        "kind": key.kind,
        "opens": key.opens,
        "status": key.status,
        "holderId": key.holder_id,
        "holderName": key.holder.name if key.holder else None,
        "depositChf": str(key.deposit_chf) if key.deposit_chf is not None else None,
        "codeId": key.code_id,
        "notes": key.notes,
        "updatedAt": key.updated_at.isoformat() if key.updated_at else None,
    }
    if with_history:
        data["history"] = [
            {
                "id": h.id,
                "action": h.action,
                "memberId": h.member_id,
                "memberName": h.member.name if h.member else None,
                "byName": h.by.name if h.by else None,
                "note": h.note,
                "at": h.at.isoformat(),
            }
            for h in key.handovers
        ]
    return data


def _clean(data: dict, partial: bool) -> dict:
    out = {k: data[k] for k in _EDITABLE if k in data}
    for k in ("label", "number", "notes"):
        if out.get(k) is not None and not isinstance(out[k], str):
            raise_error(400, "VALIDATION_ERROR", f"{k} must be text")
    if out.get("code_id") is not None and not isinstance(out["code_id"], int):
        raise_error(400, "VALIDATION_ERROR", "code_id must be a number")
    if not partial and not (data.get("label") or "").strip():
        raise_error(400, "VALIDATION_ERROR", "label is required")
    if "label" in out:
        out["label"] = (out["label"] or "").strip()
        if not out["label"]:
            raise_error(400, "VALIDATION_ERROR", "label cannot be empty")
    if "kind" in out and out["kind"] not in KEY_KINDS:
        raise_error(400, "VALIDATION_ERROR", f"kind must be one of {KEY_KINDS}")
    if "number" in out:
        out["number"] = (out["number"] or "").strip() or None
    if out.get("deposit_chf") not in (None, ""):
        try:
            out["deposit_chf"] = Decimal(str(out["deposit_chf"]))
        except InvalidOperation:
            raise_error(400, "VALIDATION_ERROR", "deposit_chf must be a number")
        if not out["deposit_chf"].is_finite():
            raise_error(400, "VALIDATION_ERROR", "deposit_chf must be a number")
    elif "deposit_chf" in out:
        out["deposit_chf"] = None
    if out.get("code_id") is not None:
        from hubra.core.models.code import Code

        if db.session.get(Code, out["code_id"]) is None:
            raise_error(404, "NOT_FOUND", f"Code {out['code_id']} not found")
    return out


def _check_number_free(number: str | None, key_id: int | None = None) -> None:
    if not number:
        return
    clash = db.session.scalar(select(Key).where(Key.number == number))
    if clash is not None and clash.id != key_id:
        raise_error(409, "CONFLICT", f"Key number {number} is already used")


class KeyService:
    @staticmethod
    def list(status: str | None = None, holder_id: int | None = None) -> list[Key]:
        stmt = select(Key).options(selectinload(Key.holder)).order_by(Key.label)
        if status:
            if status not in KEY_STATUSES:
                raise_error(400, "VALIDATION_ERROR", f"Unknown status {status}")
            stmt = stmt.where(Key.status == status)
        if holder_id is not None:
            stmt = stmt.where(Key.holder_id == holder_id)
        return list(db.session.scalars(stmt).all())

    @staticmethod
    def get(key_id: int) -> Key:
        key = db.session.get(Key, key_id)
        if key is None:
            raise_error(404, "NOT_FOUND", f"Key {key_id} not found")
        return key

    @staticmethod
    def create(data: dict, actor_id: int | None) -> Key:
        values = _clean(data, partial=False)
        _check_number_free(values.get("number"))
        key = Key(**values)
        db.session.add(key)
        db.session.flush()
        log_audit(actor_id, "create_key", "Key", key.id, key.label)
        return key

    @staticmethod
    def update(key_id: int, data: dict, actor_id: int | None) -> Key:
        key = KeyService.get(key_id)
        values = _clean(data, partial=True)
        if "number" in values:
            _check_number_free(values["number"], key.id)
        for field, value in values.items():
            setattr(key, field, value)
        db.session.flush()
        log_audit(actor_id, "update_key", "Key", key.id, key.label)
        return key

    @staticmethod
    def delete(key_id: int, actor_id: int | None) -> None:
        key = KeyService.get(key_id)
        if key.status == "issued":
            raise_error(409, "CONFLICT", "Take the key back before deleting it")
        log_audit(actor_id, "delete_key", "Key", key.id, key.label)
        db.session.delete(key)
        db.session.flush()

    # ── Handovers ──────────────────────────────────────────────────────────

    @staticmethod
    def _log(key: Key, action: str, member_id, actor_id, note) -> None:
        db.session.add(
            KeyHandover(
                key_id=key.id,
                action=action,
                member_id=member_id,
                by_id=actor_id,
                note=note,
            )
        )

    @staticmethod
    def issue(key_id: int, member_id: int, actor_id: int | None, note=None) -> Key:
        key = KeyService.get(key_id)
        if key.status != "available":
            raise_error(409, "CONFLICT", f"Key is {key.status}, not available")
        member = db.session.get(Member, member_id)
        if member is None or member.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        key.status = "issued"
        key.holder_id = member_id
        KeyService._log(key, "issue", member_id, actor_id, note)
        log_audit(actor_id, "issue_key", "Key", key.id, f"{key.label} → {member.name}")
        db.session.flush()
        return key

    @staticmethod
    def take_back(key_id: int, actor_id: int | None, note=None) -> Key:
        key = KeyService.get(key_id)
        if key.status != "issued":
            raise_error(409, "CONFLICT", "Key is not issued")
        KeyService._log(key, "return", key.holder_id, actor_id, note)
        log_audit(actor_id, "return_key", "Key", key.id, key.label)
        key.status = "available"
        key.holder_id = None
        db.session.flush()
        return key

    @staticmethod
    def mark_lost(key_id: int, actor_id: int | None, note=None) -> Key:
        key = KeyService.get(key_id)
        if key.status in ("lost", "retired"):
            raise_error(409, "CONFLICT", f"Key is already {key.status}")
        KeyService._log(key, "lost", key.holder_id, actor_id, note)
        log_audit(actor_id, "lose_key", "Key", key.id, key.label)
        key.status = "lost"
        db.session.flush()
        return key

    @staticmethod
    def mark_found(key_id: int, actor_id: int | None, note=None) -> Key:
        key = KeyService.get(key_id)
        if key.status != "lost":
            raise_error(409, "CONFLICT", "Key is not lost")
        KeyService._log(key, "found", None, actor_id, note)
        log_audit(actor_id, "find_key", "Key", key.id, key.label)
        key.status = "available"
        key.holder_id = None
        db.session.flush()
        return key

    @staticmethod
    def retire(key_id: int, actor_id: int | None, note=None) -> Key:
        key = KeyService.get(key_id)
        if key.status == "issued":
            raise_error(409, "CONFLICT", "Take the key back before retiring it")
        KeyService._log(key, "retire", None, actor_id, note)
        key.status = "retired"
        db.session.flush()
        return key
