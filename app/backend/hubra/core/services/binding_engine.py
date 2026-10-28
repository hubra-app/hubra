"""Binding engine — resolves, validates, and writes binding values.

The engine is called:
  - On binding create/update/delete/toggle (via the API service layer)
  - On source change hooks (member/group/function/mail_address/setting)
  - On source-delete guards (check for blocking enabled bindings)
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.binding import Binding
from hubra.core.models.internal_key import InternalKey
from hubra.core.services.binding_registry import (
    WRITE_ONLY_ATTRIBUTES,
    is_valid_attribute,
    resolve_source_label,
    resolve_source_value,
)
from hubra.core.services.key_service import KeyService
from hubra.core.validators import validate_value

_log = logging.getLogger(__name__)


def create_binding(
    *,
    type: str,
    source_id: str,
    source_attribute: str,
    key_id: int,
    validator: str = "none",
    enabled: bool = True,
    is_protected: bool = False,
) -> Binding:
    """Create a new binding. Validates source, attribute, and value.

    For scalar keys, rejects if an enabled binding already targets the key.
    For all keys, validates the resolved value if a validator is set.
    """
    ik = db.session.get(InternalKey, key_id)
    if ik is None:
        raise_error(404, "NOT_FOUND", f"InternalKey {key_id} not found")

    if not is_valid_attribute(type, source_attribute):
        raise_error(
            400,
            "VALIDATION_ERROR",
            f"Attribute '{source_attribute}' is not valid for type '{type}'",
        )

    existing = db.session.scalar(
        select(Binding).where(
            Binding.key_id == key_id,
            Binding.type == type,
            Binding.source_id == source_id,
            Binding.source_attribute == source_attribute,
        )
    )
    if existing is not None:
        raise_error(409, "CONFLICT", "Binding already exists")

    if enabled and not ik.allow_multiple:
        active = db.session.scalar(
            select(Binding).where(
                Binding.key_id == key_id,
                Binding.enabled.is_(True),
            )
        )
        if active is not None:
            raise_error(
                409,
                "SCALAR_KEY_OCCUPIED",
                f"Scalar key '{ik.key}' already has an enabled binding "
                f"(type={active.type}, source_id={active.source_id}). "
                "Disable it first or use an array key.",
            )

    binding = Binding(
        type=type,
        source_id=source_id,
        source_attribute=source_attribute,
        key_id=key_id,
        validator=validator,
        enabled=enabled,
        is_protected=is_protected,
        validation_status="ok",
    )
    db.session.add(binding)
    db.session.flush()

    if binding.enabled:
        sync_binding(binding)

    return binding


def update_binding(binding_id: int, **fields) -> Binding:
    """Update a binding. Protected bindings reject key_id and enabled changes."""
    binding = db.session.get(Binding, binding_id)
    if binding is None:
        raise_error(404, "NOT_FOUND", f"Binding {binding_id} not found")

    if binding.is_protected:
        if "key_id" in fields and fields["key_id"] != binding.key_id:
            raise_error(
                409, "PROTECTED", "Cannot change the key of a protected binding"
            )
        if "enabled" in fields and fields["enabled"] != binding.enabled:
            raise_error(409, "PROTECTED", "Cannot toggle a protected binding")

    old_key_id = binding.key_id
    old_enabled = binding.enabled
    key_changed = False
    source_changed = False

    if "key_id" in fields and fields["key_id"] != binding.key_id:
        new_ik = db.session.get(InternalKey, fields["key_id"])
        if new_ik is None:
            raise_error(404, "NOT_FOUND", f"InternalKey {fields['key_id']} not found")
        if not new_ik.allow_multiple:
            active = db.session.scalar(
                select(Binding).where(
                    Binding.key_id == fields["key_id"],
                    Binding.enabled.is_(True),
                    Binding.id != binding_id,
                )
            )
            if active is not None:
                raise_error(
                    409,
                    "SCALAR_KEY_OCCUPIED",
                    f"Scalar key '{new_ik.key}' already has an enabled binding",
                )
        key_changed = True

    if "type" in fields:
        binding.type = fields["type"]
        source_changed = True
    if "source_id" in fields:
        binding.source_id = fields["source_id"]
        source_changed = True
    if "source_attribute" in fields:
        binding.source_attribute = fields["source_attribute"]
        source_changed = True
    if "validator" in fields:
        binding.validator = fields["validator"]
    if "key_id" in fields:
        binding.key_id = fields["key_id"]
    if "enabled" in fields:
        binding.enabled = fields["enabled"]
    if "is_protected" in fields:
        binding.is_protected = fields["is_protected"]

    db.session.flush()

    if key_changed and old_enabled:
        sync_internal_key(old_key_id)
    if binding.enabled and (key_changed or source_changed):
        sync_binding(binding)

    return binding


def delete_binding(binding_id: int) -> None:
    """Delete a binding. Protected bindings cannot be deleted."""
    binding = db.session.get(Binding, binding_id)
    if binding is None:
        raise_error(404, "NOT_FOUND", f"Binding {binding_id} not found")

    if binding.is_protected:
        raise_error(409, "PROTECTED", "Cannot delete a protected binding")

    key_id = binding.key_id
    was_enabled = binding.enabled

    db.session.delete(binding)
    db.session.flush()

    if was_enabled:
        sync_internal_key(key_id)


def toggle_binding(binding_id: int, enabled: bool) -> Binding:
    """Enable or disable a binding. Protected bindings cannot be toggled."""
    binding = db.session.get(Binding, binding_id)
    if binding is None:
        raise_error(404, "NOT_FOUND", f"Binding {binding_id} not found")

    if binding.is_protected:
        raise_error(409, "PROTECTED", "Cannot toggle a protected binding")

    if binding.enabled == enabled:
        return binding

    if enabled and not binding.key.allow_multiple:
        active = db.session.scalar(
            select(Binding).where(
                Binding.key_id == binding.key_id,
                Binding.enabled.is_(True),
                Binding.id != binding_id,
            )
        )
        if active is not None:
            raise_error(
                409,
                "SCALAR_KEY_OCCUPIED",
                f"Scalar key '{binding.key.key}' already has an enabled binding",
            )

    binding.enabled = enabled
    db.session.flush()

    if enabled:
        sync_binding(binding)
    else:
        sync_internal_key(binding.key_id)

    return binding


def sync_binding(binding: Binding) -> None:
    """Resolve, validate, and write a single binding's value.

    For scalar keys: writes the value directly.
    For array keys: triggers a full recompute of the key.

    On validation failure: skips the write and flags the binding.
    For write-only attributes: skips write without flagging.
    """
    if not binding.enabled:
        return

    ik = binding.key

    if binding.source_attribute in WRITE_ONLY_ATTRIBUTES:
        binding.validation_status = "ok"
        binding.validation_error = None
        return

    value = resolve_source_value(
        binding.type, binding.source_id, binding.source_attribute
    )

    if value is None:
        binding.validation_status = "ok"
        binding.validation_error = None
        if ik.allow_multiple:
            sync_internal_key(binding.key_id)
        else:
            KeyService.delete(ik.key)
        return

    if binding.validator != "none":
        error = validate_value(binding.validator, value)
        if error:
            binding.validation_status = "failed"
            binding.validation_error = error[:500]
            _log.warning(
                "sync_binding: validation failed for binding %d: %s",
                binding.id,
                error,
            )
            if ik.allow_multiple:
                sync_internal_key(binding.key_id)
            else:
                KeyService.delete(ik.key)
            return

    binding.validation_status = "ok"
    binding.validation_error = None

    if ik.allow_multiple:
        sync_internal_key(binding.key_id)
    else:
        KeyService.set(ik.key, value)


def sync_internal_key(key_id: int) -> None:
    """Recompute all enabled bindings for a key.

    For scalar keys: writes the single enabled binding's value (or clears).
    For array keys: builds a deduped, stable-ordered array.
    """
    ik = db.session.get(InternalKey, key_id)
    if ik is None:
        return

    bindings = list(
        db.session.scalars(
            select(Binding)
            .where(Binding.key_id == key_id)
            .where(Binding.enabled.is_(True))
            .order_by(Binding.id)
        ).all()
    )

    if ik.allow_multiple:
        values: list[str] = []
        for b in bindings:
            if b.source_attribute in WRITE_ONLY_ATTRIBUTES:
                continue
            v = resolve_source_value(b.type, b.source_id, b.source_attribute)
            if v is None:
                continue
            if b.validator != "none":
                error = validate_value(b.validator, v)
                if error:
                    b.validation_status = "failed"
                    b.validation_error = error[:500]
                    continue
            b.validation_status = "ok"
            b.validation_error = None
            if v not in values:
                values.append(v)
        KeyService.set(ik.key, values)
    else:
        if bindings:
            b = bindings[0]
            if b.source_attribute in WRITE_ONLY_ATTRIBUTES:
                b.validation_status = "ok"
                b.validation_error = None
                return
            v = resolve_source_value(b.type, b.source_id, b.source_attribute)
            if v is None:
                KeyService.delete(ik.key)
                b.validation_status = "ok"
                b.validation_error = None
                return
            if b.validator != "none":
                error = validate_value(b.validator, v)
                if error:
                    b.validation_status = "failed"
                    b.validation_error = error[:500]
                    KeyService.delete(ik.key)
                    return
            b.validation_status = "ok"
            b.validation_error = None
            KeyService.set(ik.key, v)
        else:
            KeyService.delete(ik.key)


def sync_for_source(binding_type: str, source_id: str) -> None:
    """Sync all enabled bindings for a given source."""
    bindings = list(
        db.session.scalars(
            select(Binding)
            .where(Binding.type == binding_type)
            .where(Binding.source_id == source_id)
            .where(Binding.enabled.is_(True))
        ).all()
    )
    for b in bindings:
        sync_binding(b)


def check_source_delete_blocked(binding_type: str, source_id: str) -> list[Binding]:
    """Return enabled bindings that block deletion of the source."""
    return list(
        db.session.scalars(
            select(Binding)
            .where(Binding.type == binding_type)
            .where(Binding.source_id == source_id)
            .where(Binding.enabled.is_(True))
        ).all()
    )


def check_mail_address_delete_blocked_for_owner(
    owner_type: str, owner_id: int
) -> list[Binding]:
    """Check if any enabled mail_address bindings block deletion of an owner entity.

    Looks up all ManagedMailAddress rows linked to the owner and checks
    each for enabled bindings.
    """
    from hubra.core.models.managed_mail import ManagedMailAddress

    if owner_type == "member":
        mmas = list(
            db.session.scalars(
                select(ManagedMailAddress).where(
                    ManagedMailAddress.owner_type == "member",
                    ManagedMailAddress.owner_id == owner_id,
                )
            ).all()
        )
    elif owner_type == "group":
        mmas = list(
            db.session.scalars(
                select(ManagedMailAddress).where(
                    ManagedMailAddress.owner_type == "group",
                    ManagedMailAddress.owner_id == owner_id,
                )
            ).all()
        )
    elif owner_type == "function":
        mmas = list(
            db.session.scalars(
                select(ManagedMailAddress).where(
                    ManagedMailAddress.owner_type == "function",
                    ManagedMailAddress.owner_id == owner_id,
                )
            ).all()
        )
    else:
        return []

    blocked: list[Binding] = []
    for mma in mmas:
        blocked.extend(check_source_delete_blocked("mail_address", str(mma.id)))
    return blocked


def cascade_delete_disabled(binding_type: str, source_id: str) -> None:
    """Delete all disabled bindings for a source (called on source delete)."""
    bindings = list(
        db.session.scalars(
            select(Binding)
            .where(Binding.type == binding_type)
            .where(Binding.source_id == source_id)
            .where(Binding.enabled.is_(False))
        ).all()
    )
    for b in bindings:
        db.session.delete(b)


def assert_source_deletable(binding_type: str, source_id: str) -> None:
    """Raise 409 if enabled bindings block deletion of the source."""
    blocked = check_source_delete_blocked(binding_type, source_id)
    if blocked:
        descriptions = []
        for b in blocked:
            label = resolve_source_label(b.type, b.source_id) or b.source_id
            ik = b.key
            descriptions.append(
                f"Binding #{b.id}: {b.type}.{label}.{b.source_attribute} → {ik.key}"
            )
        raise_error(
            409,
            "SOURCE_HAS_BINDINGS",
            "Cannot delete: enabled bindings reference this source. "
            "Disable or remove them first: " + "; ".join(descriptions),
        )


def assert_mail_address_owner_deletable(owner_type: str, owner_id: int) -> None:
    """Raise 409 if enabled mail_address bindings block deletion of an owner."""
    blocked = check_mail_address_delete_blocked_for_owner(owner_type, owner_id)
    if blocked:
        descriptions = []
        for b in blocked:
            label = resolve_source_label(b.type, b.source_id) or b.source_id
            ik = b.key
            descriptions.append(
                f"Binding #{b.id}: {b.type}.{label}.{b.source_attribute} → {ik.key}"
            )
        raise_error(
            409,
            "SOURCE_HAS_BINDINGS",
            "Cannot delete: enabled mail_address bindings reference addresses "
            "owned by this entity. Disable or remove them first: "
            + "; ".join(descriptions),
        )
