"""Per-type attribute registry for the binding system.

Defines which source attributes are available for each binding type,
and how to resolve their current values.

Attributes are derived **dynamically** from each model's
``SQLAlchemyAutoSchema`` (introspecting field names), supplemented with
virtual/linked attributes for backward compatibility and MMA linkage.

Supported binding types:
  member | group | function | setting | mail_address

Virtual attribute patterns:
  - ``primary_mail_address`` / ``private_mail`` / ``member_number`` (member legacy)
  - ``primary_alias`` (group/function legacy)
  - ``mma.<sub_attr>`` — resolves a sub-attribute on the entity's primary MMA
  - ``additional_alias:<id>`` — resolves an additional alias address by id
    (MailAlias row or additional MMA row); valid for member/group/function
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select

from vollbuild.extensions import db

_log = logging.getLogger(__name__)

_SENSITIVE_PATTERN = re.compile(r"password|secret|token|credential", re.IGNORECASE)


def is_sensitive_attribute(binding_type: str, source_attribute: str) -> bool:
    """True if the attribute name itself denotes sensitive data."""
    return bool(_SENSITIVE_PATTERN.search(source_attribute))


def is_sensitive_value(
    binding_type: str, source_id: str, source_attribute: str
) -> bool:
    """True if the resolved value for this source should be masked.

    For settings, sensitivity is per-record (Setting.sensitive).
    For other types, it's determined by the attribute name.
    """
    if binding_type == "setting":
        from vollbuild.core.models.setting import Setting

        s = db.session.get(Setting, source_id)
        return s is not None and s.sensitive
    return is_sensitive_attribute(binding_type, source_attribute)


# ── Per-type blocklists (schema fields excluded from binding attributes) ─────

_BLOCKLIST: dict[str, frozenset[str]] = {
    "member": frozenset(
        {
            "id",
            "tier",
            "role",
            "group_ids",
            "avatar",
            "avatar_color",
            "must_change_password",
            "is_disabled",
            "last_seen",
            "last_login_ip",
            "last_login_ua",
            "failed_login_count",
            "locked_until",
            "private_email_verified",
            "inbound_count",
            "archived_at",
            "created_at",
            "updated_at",
            "password_hash",
            "club_username",
        }
    ),
    "group": frozenset(
        {
            "id",
            "members",
            "lead",
            "member_count",
            "lead_name",
            "created_at",
            "updated_at",
        }
    ),
    "function": frozenset({"id", "holders", "created_at", "updated_at"}),
    "mail_address": frozenset(
        {
            "id",
            "is_system",
            "address_type",
            "is_protected",
            "forwarding_enabled",
            "is_enabled",
            "cached_forward_targets",
            "fixed_forward_targets",
            "provisioning_status",
            "wildduck_user_id",
            "wildduck_filter_id",
            "kind",
            "owner_type",
            "owner_id",
            "forward_enabled",
            "quota_bytes",
            "retention",
            "from_whitelist",
            "last_quota_alert_at",
            "wildduck_id",
            "wildduck_type",
            "last_synced_at",
            "sync_state",
            "sync_error",
            "mailbox_password_encrypted",
            "created_at",
            "updated_at",
            "mail_prefix",
            "display_name",
            "domain",
            "aliases",
        }
    ),
}

# ── Virtual attributes (not from schema introspection) ──────────────────────
#
# Legacy compat + MMA linkage + mail_address password.
# ``mma.password`` is member-only (members have mailbox-type MMAs;
# group/function alias-type MMAs never carry a password).

_VIRTUAL_ATTRIBUTES: dict[str, dict[str, str]] = {
    "member": {
        "primary_mail_address": "Primary mail address",
        "private_mail": "Private email",
        "member_number": "Member number",
        "mma.address": "Linked mailbox: address",
        "mma.local_part": "Linked mailbox: local part",
        "mma.enabled": "Linked mailbox: enabled state",
        "mma.password": "Linked mailbox: password",
    },
    "group": {
        "primary_alias": "Primary alias address",
        "mma.address": "Linked mailbox: address",
        "mma.local_part": "Linked mailbox: local part",
        "mma.enabled": "Linked mailbox: enabled state",
    },
    "function": {
        "primary_alias": "Primary alias address",
        "mma.address": "Linked mailbox: address",
        "mma.local_part": "Linked mailbox: local part",
        "mma.enabled": "Linked mailbox: enabled state",
    },
    "setting": {
        "value": "Setting value",
    },
    "mail_address": {
        "address": "Full address",
        "local_part": "Local part",
        "enabled": "Enabled state",
        "password": "System mailbox password",
    },
}

# Schema class path per binding type (lazy-imported to avoid circular imports).
_SCHEMA_MAP: dict[str, str] = {
    "member": "vollbuild.schemas.member.MemberSchema",
    "group": "vollbuild.schemas.group.GroupSchema",
    "function": "vollbuild.schemas.function.FunctionSchema",
    "mail_address": "vollbuild.schemas.managed_mail.ManagedMailAddressSchema",
}

# Field types from marshmallow that represent simple scalar values suitable
# for binding attributes. Nested/List/Dict are excluded.
_SCALAR_FIELD_TYPES = frozenset(
    {
        "String",
        "Boolean",
        "Date",
        "DateTime",
        "Integer",
        "Float",
        "Decimal",
        "Method",
        "Function",
        "Constant",
    }
)

# Attributes that are write-only: the binding engine skips value resolution
# and never writes them to a key.  Currently empty — ``password`` is now
# resolved from encrypted storage (see ``_resolve_mail_address``).
WRITE_ONLY_ATTRIBUTES: frozenset[str] = frozenset()

# Cache for the built registry (rebuilt on first access).
_REGISTRY_CACHE: dict[str, dict[str, str]] | None = None


def _make_label(field_name: str) -> str:
    """Convert a snake_case field name to a human-readable label."""
    return field_name.replace("_", " ").capitalize()


def _schema_fields(binding_type: str) -> dict[str, str]:
    """Introspect the SQLAlchemyAutoSchema for *binding_type*.

    Returns ``{field_name: label}`` for scalar, non-blocklisted fields.
    """
    import importlib

    dotted = _SCHEMA_MAP.get(binding_type)
    if dotted is None:
        return {}

    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    schema_cls = getattr(module, class_name)
    schema = schema_cls()

    blocklist = _BLOCKLIST.get(binding_type, frozenset())
    result: dict[str, str] = {}
    for name, field in schema.fields.items():
        if name in blocklist:
            continue
        type_name = type(field).__name__
        if type_name not in _SCALAR_FIELD_TYPES:
            continue
        result[name] = _make_label(name)
    return result


def build_attribute_registry() -> dict[str, dict[str, str]]:
    """Build the full attribute registry (schema-derived + virtual).

    Virtual attributes take precedence (they have curated labels).
    Schema-derived fields are appended if not already present.
    """
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE

    registry: dict[str, dict[str, str]] = {}
    for btype in ("member", "group", "function", "setting", "mail_address"):
        attrs: dict[str, str] = {}
        # Virtual attributes first (take precedence)
        attrs.update(_VIRTUAL_ATTRIBUTES.get(btype, {}))
        # Schema-derived fields (skip duplicates)
        if btype in _SCHEMA_MAP:
            for name, label in _schema_fields(btype).items():
                if name not in attrs:
                    attrs[name] = label
        registry[btype] = attrs

    _REGISTRY_CACHE = registry
    return registry


def get_attributes_for_type(binding_type: str) -> dict[str, str]:
    """Return the attribute -> label map for the given type."""
    return build_attribute_registry().get(binding_type, {})


def is_valid_attribute(binding_type: str, attribute: str) -> bool:
    """Check if an attribute is valid for the given type.

    Supports:
    - Schema-derived and virtual attributes from the registry.
    - Dynamic ``additional_alias:<id>`` attributes for member/group/function.
    """
    registry = build_attribute_registry().get(binding_type, {})
    if attribute in registry:
        return True
    if binding_type in ("member", "group", "function") and attribute.startswith(
        "additional_alias:"
    ):
        return True
    return False


# ── Value resolution ─────────────────────────────────────────────────────────


def resolve_source_value(
    binding_type: str, source_id: str, source_attribute: str
) -> str | None:
    """Resolve the current value of a source attribute.

    Returns the plain string value, or ``None`` if the source or attribute
    cannot be resolved.
    """
    if source_attribute in WRITE_ONLY_ATTRIBUTES:
        return None

    # Virtual / legacy attributes
    if binding_type == "member":
        return _resolve_member(source_id, source_attribute)
    elif binding_type == "group":
        return _resolve_group(source_id, source_attribute)
    elif binding_type == "function":
        return _resolve_function(source_id, source_attribute)
    elif binding_type == "setting":
        return _resolve_setting(source_id, source_attribute)
    elif binding_type == "mail_address":
        return _resolve_mail_address(source_id, source_attribute)

    return None


def _resolve_member(source_id: str, attribute: str) -> str | None:
    from vollbuild.core.models.member import Member

    member = db.session.get(Member, int(source_id))
    if member is None:
        return None
    if attribute == "primary_mail_address":
        return member.public_email
    if attribute == "private_mail":
        return member.email
    if attribute == "member_number":
        return str(member.id)
    if attribute == "name":
        return member.name
    if attribute.startswith("mma."):
        return _resolve_mma_attribute("member", member.id, attribute)
    if attribute.startswith("additional_alias:"):
        return _resolve_additional_alias("member", member.id, attribute)
    # Schema-derived attribute
    return _resolve_schema_attribute(member, attribute)


def _projected_mma_values(name: str) -> dict[str, str | None]:
    """Compute what MMA address/local_part would be, even without an MMA row.

    Used as a fallback when a group/function has no MMA yet, so binding
    previews show the projected address instead of empty.
    """
    from vollbuild.api.settings.services import SettingService
    from vollbuild.core.services.managed_mail import normalize_prefix_from_name

    club_domain = SettingService.get("mail.domain") or ""
    prefix = normalize_prefix_from_name(name)
    address = f"{prefix}@{club_domain}"
    return {
        "address": address,
        "local_part": prefix,
        "enabled": "false",
    }


def _resolve_group(source_id: str, attribute: str) -> str | None:
    from vollbuild.core.models.group import Group

    group = db.session.get(Group, int(source_id))
    if group is None:
        return None
    if attribute == "name":
        return group.name
    if attribute == "primary_alias":
        mma = _get_primary_mma("group", group.id)
        if mma:
            return mma.address
        return _projected_mma_values(group.name)["address"]
    if attribute.startswith("mma."):
        mma = _get_primary_mma("group", group.id)
        if mma:
            return _resolve_mma_attribute("group", group.id, attribute)
        sub = attribute.split(".", 1)[1] if "." in attribute else attribute
        return _projected_mma_values(group.name).get(sub)
    if attribute.startswith("additional_alias:"):
        return _resolve_additional_alias("group", group.id, attribute)
    # Schema-derived attribute
    return _resolve_schema_attribute(group, attribute)


def _resolve_function(source_id: str, attribute: str) -> str | None:
    from vollbuild.core.models.function import Function

    fn = db.session.get(Function, int(source_id))
    if fn is None:
        return None
    if attribute == "name":
        return fn.name
    if attribute == "primary_alias":
        mma = _get_primary_mma("function", fn.id)
        if mma:
            return mma.address
        return _projected_mma_values(fn.name)["address"]
    if attribute.startswith("mma."):
        mma = _get_primary_mma("function", fn.id)
        if mma:
            return _resolve_mma_attribute("function", fn.id, attribute)
        sub = attribute.split(".", 1)[1] if "." in attribute else attribute
        return _projected_mma_values(fn.name).get(sub)
    if attribute.startswith("additional_alias:"):
        return _resolve_additional_alias("function", fn.id, attribute)
    # Schema-derived attribute
    return _resolve_schema_attribute(fn, attribute)


def _resolve_setting(source_id: str, attribute: str) -> str | None:
    from vollbuild.api.settings.services import SettingService

    if attribute == "value":
        return SettingService.get(source_id)
    return None


def _resolve_mail_address(source_id: str, attribute: str) -> str | None:
    from vollbuild.core.models.managed_mail import ManagedMailAddress

    mma = db.session.get(ManagedMailAddress, int(source_id))
    if mma is None:
        return None
    if attribute == "address":
        return mma.address
    if attribute == "local_part":
        return mma.local_part
    if attribute == "enabled":
        enabled = mma.enabled
        if enabled is None:
            enabled = mma.is_enabled
        return str(enabled) if enabled is not None else None
    if attribute == "password":
        return _resolve_mailbox_password(mma)
    # Schema-derived attribute
    return _resolve_schema_attribute(mma, attribute)


# ── Helpers for MMA linkage ──────────────────────────────────────────────────


def _get_primary_mma(owner_type: str, owner_id: int):
    """Return the primary MMA for an entity (fixed_forward_targets is None)."""
    from vollbuild.core.models.managed_mail import ManagedMailAddress

    return db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == owner_type,
            ManagedMailAddress.owner_id == owner_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )


def _resolve_mma_attribute(
    owner_type: str, owner_id: int, attribute: str
) -> str | None:
    """Resolve an ``mma.<sub_attr>`` attribute on an entity's primary MMA."""
    mma = _get_primary_mma(owner_type, owner_id)
    if mma is None:
        return None

    sub = attribute.split(".", 1)[1] if "." in attribute else attribute
    if sub == "address":
        return mma.address
    if sub == "local_part":
        return mma.local_part
    if sub == "enabled":
        enabled = mma.enabled
        if enabled is None:
            enabled = mma.is_enabled
        return str(enabled) if enabled is not None else None
    if sub == "password":
        # mma.password is only valid for member (mailbox-type MMAs).
        # Alias-type MMAs (group/function) never have a password.
        if owner_type != "member":
            return None
        return _resolve_mailbox_password(mma)
    return None


def _resolve_mailbox_password(mma) -> str | None:
    """Decrypt and return the stored mailbox password, or None."""
    from vollbuild.crypto import decrypt_code

    if not mma.mailbox_password_encrypted:
        return None
    try:
        return decrypt_code(mma.mailbox_password_encrypted)
    except Exception:
        _log.warning("resolve_mailbox_password: failed to decrypt for MMA %s", mma.id)
        return None


def _resolve_additional_alias(
    owner_type: str, owner_id: int, attribute: str
) -> str | None:
    """Resolve an ``additional_alias:<id>`` attribute.

    Queries MMA rows with owner_type='mail_address' (unified alias model)
    or additional MMA rows owned directly by the entity.
    """
    from vollbuild.core.models.managed_mail import ManagedMailAddress

    alias_id_str = attribute.split(":", 1)[1]
    try:
        alias_id = int(alias_id_str)
    except ValueError:
        return None

    # Try alias MMA row (owner_type='mail_address' linked to primary MMA)
    addr = db.session.get(ManagedMailAddress, alias_id)
    if addr is not None:
        # Check if it's a child alias of this entity's primary MMA
        mma = _get_primary_mma(owner_type, owner_id)
        if (
            mma is not None
            and addr.owner_type == "mail_address"
            and addr.owner_id == mma.id
        ):
            return addr.address
        # Check if it's an additional MMA row owned directly by the entity
        if (
            addr.owner_type == owner_type
            and addr.owner_id == owner_id
            and addr.fixed_forward_targets is not None
        ):
            return addr.address
        # If the alias exists but isn't linked to this entity, still return it
        # — the binding was valid when created
        return addr.address

    return None


def _resolve_schema_attribute(instance, attribute: str) -> str | None:
    """Resolve a schema-derived attribute via getattr on the model instance."""
    value = getattr(instance, attribute, None)
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return None
    return str(value)


# ── Source labels ────────────────────────────────────────────────────────────


def resolve_source_label(binding_type: str, source_id: str) -> str | None:
    """Return a human-readable label for the source record."""
    if binding_type == "member":
        from vollbuild.core.models.member import Member

        m = db.session.get(Member, int(source_id))
        return m.name if m else None
    elif binding_type == "group":
        from vollbuild.core.models.group import Group

        g = db.session.get(Group, int(source_id))
        return g.name if g else None
    elif binding_type == "function":
        from vollbuild.core.models.function import Function

        f = db.session.get(Function, int(source_id))
        return f.name if f else None
    elif binding_type == "setting":
        return source_id
    elif binding_type == "mail_address":
        from vollbuild.core.models.managed_mail import ManagedMailAddress

        mma = db.session.get(ManagedMailAddress, int(source_id))
        return mma.address if mma else None
    return None
