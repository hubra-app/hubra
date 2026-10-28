"""Bindings API services — serialization and listing helpers.

Business logic (create/update/delete/toggle/sync) lives in the binding engine.
This module handles serialization (masking sensitive values) and DB queries for listing.
"""

from __future__ import annotations

from sqlalchemy import select

from vollbuild.extensions import db
from vollbuild.core.models.binding import Binding
from vollbuild.core.models.internal_key import InternalKey
from vollbuild.core.services.binding_registry import (
    build_attribute_registry,
    is_sensitive_value,
    resolve_source_label,
    resolve_source_value,
    WRITE_ONLY_ATTRIBUTES,
)
from vollbuild.core.services.key_service import KeyService
from vollbuild.validators import VALIDATORS

_MASK = "\u2022" * 8


def _is_key_sensitive(ik: InternalKey) -> bool:
    """Determine if a key's value should be masked based on its enabled bindings."""
    bindings = list(
        db.session.scalars(
            select(Binding).where(Binding.key_id == ik.id, Binding.enabled.is_(True))
        ).all()
    )
    if not bindings:
        return True
    return any(
        is_sensitive_value(b.type, b.source_id, b.source_attribute) for b in bindings
    )


def _key_display_value(ik: InternalKey) -> str | None:
    """Decrypt and format a key's value for display."""
    raw = KeyService.get(ik.key)
    if raw is None:
        return None
    if isinstance(raw, list):
        return ", ".join(raw) if raw else None
    return raw


def serialize_key(ik: InternalKey) -> dict:
    has_value = ik.value is not None
    sensitive = True
    display = None
    if has_value:
        sensitive = _is_key_sensitive(ik)
        if not sensitive:
            plain = _key_display_value(ik)
            display = plain if plain is not None else _MASK
        else:
            display = _MASK
    return {
        "id": ik.id,
        "key": ik.key,
        "allow_multiple": ik.allow_multiple,
        "is_protected": ik.is_protected,
        "label": ik.label,
        "has_value": has_value,
        "masked_value": display,
        "sensitive": sensitive,
        "created_at": ik.created_at.isoformat() if ik.created_at else None,
        "updated_at": ik.updated_at.isoformat() if ik.updated_at else None,
    }


def serialize_binding(b: Binding) -> dict:
    resolved = None
    resolved_sensitive = False
    if b.source_attribute not in WRITE_ONLY_ATTRIBUTES:
        raw = resolve_source_value(b.type, b.source_id, b.source_attribute)
        if raw is not None:
            resolved_sensitive = is_sensitive_value(
                b.type, b.source_id, b.source_attribute
            )
            resolved = _MASK if resolved_sensitive else raw

    ik = b.key
    return {
        "id": b.id,
        "type": b.type,
        "source_id": b.source_id,
        "source_attribute": b.source_attribute,
        "key_id": b.key_id,
        "key_name": ik.key if ik else None,
        "allow_multiple": ik.allow_multiple if ik else False,
        "validator": b.validator,
        "is_protected": b.is_protected,
        "enabled": b.enabled,
        "validation_status": b.validation_status,
        "validation_error": b.validation_error,
        "source_label": resolve_source_label(b.type, b.source_id),
        "resolved_value": resolved,
        "resolved_sensitive": resolved_sensitive,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def preview_source_value(
    binding_type: str, source_id: str, source_attribute: str
) -> dict:
    """Resolve a source value for preview, masking if sensitive."""
    sensitive = is_sensitive_value(binding_type, source_id, source_attribute)
    if source_attribute in WRITE_ONLY_ATTRIBUTES:
        return {"value": None, "masked": False, "sensitive": sensitive}
    raw = resolve_source_value(binding_type, source_id, source_attribute)
    if raw is None:
        return {"value": None, "masked": False, "sensitive": sensitive}
    if sensitive:
        return {"value": _MASK, "masked": True, "sensitive": True}
    return {"value": raw, "masked": False, "sensitive": False}


def list_keys() -> list[dict]:
    iks = list(db.session.scalars(select(InternalKey).order_by(InternalKey.key)).all())
    return [serialize_key(ik) for ik in iks]


def get_key(key_id: int) -> InternalKey | None:
    return db.session.get(InternalKey, key_id)


def list_bindings(
    *, key_id: int | None = None, binding_type: str | None = None
) -> list[dict]:
    stmt = select(Binding).order_by(Binding.id)
    if key_id is not None:
        stmt = stmt.where(Binding.key_id == key_id)
    if binding_type is not None:
        stmt = stmt.where(Binding.type == binding_type)
    bindings = list(db.session.scalars(stmt).all())
    return [serialize_binding(b) for b in bindings]


def get_registry() -> list[dict]:
    result = []
    for btype, attrs in build_attribute_registry().items():
        result.append(
            {
                "type": btype,
                "attributes": [
                    {"name": name, "label": label} for name, label in attrs.items()
                ],
            }
        )
    return result


def get_validators() -> list[str]:
    return sorted(VALIDATORS.keys())


def get_key_bindings_count(key_id: int) -> int:
    return (
        db.session.scalar(
            select(db.func.count()).select_from(Binding).where(Binding.key_id == key_id)
        )
        or 0
    )


def list_sources(binding_type: str) -> list[dict]:
    """List available source records for a binding type.

    Returns ``[{id, label, preview: {field: value, ...}, aliases: [{id, address}, ...]}]``.

    For member/group/function, ``preview`` includes the primary MMA address
    (if any) and ``aliases`` lists additional alias addresses (MailAlias
    children + additional MMA rows) bindable via ``additional_alias:<id>``.
    Password is never included in any preview or alias list.
    """
    if binding_type == "member":
        from vollbuild.core.models.member import Member
        from vollbuild.core.models.user import User

        members = list(
            db.session.scalars(
                select(Member)
                .join(User, Member.user_id == User.id, isouter=True)
                .order_by(User.first_name, User.last_name)
            ).all()
        )
        return [
            {
                "id": str(m.id),
                "label": m.name,
                "preview": _member_preview(m),
                "aliases": _get_source_aliases("member", m.id),
            }
            for m in members
        ]

    if binding_type == "group":
        from vollbuild.core.models.group import Group

        groups = list(db.session.scalars(select(Group).order_by(Group.name)).all())
        return [
            {
                "id": str(g.id),
                "label": g.name,
                "preview": _group_preview(g),
                "aliases": _get_source_aliases("group", g.id),
            }
            for g in groups
        ]

    if binding_type == "function":
        from vollbuild.core.models.function import Function

        fns = list(db.session.scalars(select(Function).order_by(Function.name)).all())
        return [
            {
                "id": str(f.id),
                "label": f.name,
                "preview": _function_preview(f),
                "aliases": _get_source_aliases("function", f.id),
            }
            for f in fns
        ]

    if binding_type == "setting":
        from vollbuild.core.models.setting import Setting

        settings = list(db.session.scalars(select(Setting).order_by(Setting.key)).all())
        return [
            {
                "id": s.key,
                "label": s.key,
                "preview": {
                    "key": s.key,
                    "value": _MASK if s.sensitive else s.value,
                    "namespace": s.namespace,
                    "sensitive": s.sensitive,
                },
            }
            for s in settings
        ]

    if binding_type == "mail_address":
        from vollbuild.core.models.managed_mail import ManagedMailAddress

        mmas = list(
            db.session.scalars(
                select(ManagedMailAddress).order_by(ManagedMailAddress.address)
            ).all()
        )
        return [
            {
                "id": str(mma.id),
                "label": mma.address,
                "preview": {
                    "address": mma.address,
                    "local_part": mma.local_part,
                    "is_enabled": mma.is_enabled,
                    "address_type": mma.address_type,
                },
            }
            for mma in mmas
        ]

    return []


def _member_preview(member) -> dict:
    from vollbuild.core.services.binding_registry import _get_primary_mma

    mma = _get_primary_mma("member", member.id)
    return {
        "name": member.name,
        "email": member.email,
        "public_email": member.public_email,
        "status": member.status,
        "mma_address": mma.address if mma else None,
    }


def _group_preview(group) -> dict:
    from vollbuild.core.services.binding_registry import _get_primary_mma

    mma = _get_primary_mma("group", group.id)
    return {
        "name": group.name,
        "description": group.description,
        "mma_address": mma.address if mma else None,
    }


def _function_preview(fn) -> dict:
    from vollbuild.core.services.binding_registry import _get_primary_mma

    mma = _get_primary_mma("function", fn.id)
    return {
        "name": fn.name,
        "description": fn.description,
        "mma_address": mma.address if mma else None,
    }


def _get_source_aliases(owner_type: str, owner_id: int) -> list[dict]:
    """Return additional alias addresses for an entity.

    Combines:
    - Alias MMA rows linked to the entity's primary MMA (owner_type='mail_address')
    - Additional MMA rows owned by the entity with fixed_forward_targets set

    Returns ``[{"id": <id>, "address": "<address>"}]`` sorted by address.
    """
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.services.binding_registry import _get_primary_mma

    aliases: list[dict] = []

    primary_mma = _get_primary_mma(owner_type, owner_id)
    if primary_mma is not None:
        child_aliases = list(
            db.session.scalars(
                select(ManagedMailAddress)
                .where(
                    ManagedMailAddress.owner_type == "mail_address",
                    ManagedMailAddress.owner_id == primary_mma.id,
                )
                .order_by(ManagedMailAddress.address)
            ).all()
        )
        for a in child_aliases:
            aliases.append({"id": a.id, "address": a.address})

    additional_mmas = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(
                ManagedMailAddress.owner_type == owner_type,
                ManagedMailAddress.owner_id == owner_id,
                ManagedMailAddress.fixed_forward_targets.is_not(None),
            )
            .order_by(ManagedMailAddress.address)
        ).all()
    )
    for mma in additional_mmas:
        aliases.append({"id": mma.id, "address": mma.address})

    aliases.sort(key=lambda a: a["address"])
    return aliases
