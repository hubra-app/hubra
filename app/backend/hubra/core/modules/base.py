"""Module manifest types.

A module is one section of the suite (members, finance, inventory, ...).
Each module declares a manifest: its blueprints, permissions, settings
schema, nav entries, dependencies and event subscriptions.  The registry
(``hubra.core.modules.registry``) is built from these manifests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SETTING_TYPES = {"str", "int", "bool", "float", "secret", "url", "email", "choice"}


@dataclass(frozen=True)
class Blueprint:
    """A Flask blueprint owned by a module.

    ``v2`` is ignored. The /api/v2 aliases were removed; the field stays so
    plugins built before that still load.

    ``perm_prefix`` replaces the first part of the permission keys the
    blueprint's routes check, which is otherwise the Flask blueprint's name
    without ``_bp``. It lets a plugin take over routes of a module it extends
    and keep their keys (``finance.transactions.read``), so roles don't
    change. Plugins may only name a module they depend on
    (``hubra.core.plugins.limits``).

    A backend registers only the blueprints of the API area its role serves
    (``hubra.core.roles.registers``), found from ``url_prefix``. ``shared``
    marks one every role registers: the probes, the version and the OAuth
    server metadata.
    """

    import_path: str
    attr: str
    url_prefix: str
    v2: tuple[tuple[str, str], ...] = ()
    perm_prefix: str | None = None
    shared: bool = False


@dataclass(frozen=True)
class NavItem:
    """A sidebar entry.  ``icon`` is a name the frontend maps to an icon."""

    path: str
    label_key: str
    icon: str
    # Sidebar area (workspace, activities, operations, system, me). "more"
    # files a plugin's page under the sidebar's "Erweiterungen" area; every
    # page also has a card on the "Weitere" overview.
    section: str = "workspace"
    order: int = 100
    perms: tuple[str, ...] = ()
    # Items sharing a group collapse into the first visible one, for
    # screens that host several modules as tabs (events, polls, posts).
    group: str | None = None
    # Path of the entry whose screen shows this one as a tab, instead of a
    # sidebar row of its own, for pages that belong together (members with
    # functions, tiers and groups; settings with roles and the audit log).
    parent: str | None = None


@dataclass(frozen=True)
class SettingField:
    """One per-tenant setting of a module, stored in ``TenantFeature.config``."""

    key: str
    type: str = "str"
    default: Any = None
    label: str = ""
    description: str = ""
    required: bool = False
    choices: tuple[str, ...] = ()

    def __post_init__(self):
        if self.type not in _SETTING_TYPES:
            raise ValueError(f"SettingField {self.key}: unknown type {self.type!r}")

    def coerce(self, value: Any) -> Any:
        """Convert *value* to this field's type, raising ValueError if invalid."""
        if value is None or value == "":
            if self.required:
                raise ValueError(f"{self.key} is required")
            return self.default
        if self.type == "bool":
            if isinstance(value, bool):
                return value
            if str(value).lower() in ("1", "true", "yes", "on"):
                return True
            if str(value).lower() in ("0", "false", "no", "off"):
                return False
            raise ValueError(f"{self.key} must be true or false")
        if self.type == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{self.key} must be a whole number") from None
        if self.type == "float":
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{self.key} must be a number") from None
        value = str(value).strip()
        if self.type == "url" and not value.startswith(("https://", "http://")):
            raise ValueError(f"{self.key} must start with https://")
        if self.type == "email" and "@" not in value:
            raise ValueError(f"{self.key} must be an email address")
        if self.type == "choice" and value not in self.choices:
            raise ValueError(f"{self.key} must be one of {', '.join(self.choices)}")
        return value

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "type": self.type,
            "default": None if self.type == "secret" else self.default,
            "label": self.label or self.key,
            "description": self.description,
            "required": self.required,
            "choices": list(self.choices),
        }


@dataclass(frozen=True)
class Schedule:
    """A periodic Celery task the beat scheduler runs every *every* seconds.

    The task body is usually wrapped in ``@per_tenant_job`` so it runs once
    per club that has the module on.
    """

    name: str
    task: str
    every: float


@dataclass(frozen=True)
class AppScope:
    """One thing a connected app may do, shown to the admin who connects it."""

    key: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class AppProvider:
    """An outside service a club can connect (Einstellungen > Verbundene Apps).

    ``handler`` is a dotted ``module.path:object`` with the provider's hooks;
    see ``hubra.core.apps`` for which ones exist.
    """

    code: str
    name: str
    handler: str
    description: str = ""
    icon: str = "plug"
    scopes: tuple[AppScope, ...] = ()

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "scopes": [
                {"key": s.key, "label": s.label, "description": s.description}
                for s in self.scopes
            ],
        }


@dataclass(frozen=True)
class Module:
    """A module manifest.

    ``required`` modules are always on and cannot be switched off.
    ``public_endpoints`` lists endpoint names (``bp.view``) that stay
    reachable while the module is off, such as a health check.
    ``tables`` lists the tenant-schema tables the module owns, so new
    tenant schemas clone them.
    ``events`` maps an event name to a dotted ``module.path:function``
    that is called when the event is emitted for a tenant that has this
    module enabled.
    ``tasks`` lists Python modules with Celery tasks for the worker to load.
    ``schedule`` lists periodic tasks for the beat scheduler.
    ``apps`` lists outside services a club can connect through this module.
    ``processes`` maps a name to a dotted ``module.path:function`` that runs
    as its own long-lived process (``flask modules run <name>``), such as a
    connection to a chat service's gateway; one per platform, not per club.
    ``plugin`` is the id of the plugin that brought the module (set by the
    plugin loader; ``None`` for modules built into Hubra).
    ``events_in_transaction`` lists events whose handlers run inside the
    caller's transaction, as Hubra's own modules' always do. A plugin's
    other handlers run after the commit, in the worker. Honoured for
    official plugins only (``hubra.core.plugins.limits``).
    """

    code: str
    name: str
    description: str = ""
    depends_on: tuple[str, ...] = ()
    default_enabled: bool = False
    required: bool = False
    blueprints: tuple[Blueprint, ...] = ()
    nav: tuple[NavItem, ...] = ()
    settings: tuple[SettingField, ...] = ()
    events: dict[str, str] = field(default_factory=dict)
    public_endpoints: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    # Encrypted columns this module stores, (table, primary key, column,
    # extra WHERE), so key checks and FERNET_KEY rotation re-encrypt them.
    encrypted_columns: tuple[tuple[str, str, str, str], ...] = ()
    # Rights no single route stands for (a route checks them itself), as
    # (key, display name), e.g. ("inventory.items.create_own", "Add own items").
    permissions: tuple[tuple[str, str], ...] = ()
    # Fields a role may be allowed to update one by one, as (blueprint,
    # resource, field, display name); the key is <bp>.<resource>.update.<field>.
    field_permissions: tuple[tuple[str, str, str, str], ...] = ()
    tasks: tuple[str, ...] = ()
    schedule: tuple[Schedule, ...] = ()
    apps: tuple[AppProvider, ...] = ()
    processes: dict[str, str] = field(default_factory=dict)
    events_in_transaction: tuple[str, ...] = ()
    plugin: str | None = None

    def setting(self, key: str) -> SettingField | None:
        return next((s for s in self.settings if s.key == key), None)

    def validate_config(self, config: dict | None) -> dict:
        """Return *config* coerced against the settings schema.

        Unknown keys are rejected.  Secret fields that are sent empty keep
        their previous value, which the caller merges in.
        """
        config = dict(config or {})
        unknown = set(config) - {s.key for s in self.settings}
        if unknown:
            raise ValueError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        return {s.key: s.coerce(config.get(s.key)) for s in self.settings}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "dependsOn": list(self.depends_on),
            "required": self.required,
            "defaultEnabled": self.default_enabled,
            "plugin": self.plugin,
            "nav": [
                {
                    "path": n.path,
                    "labelKey": n.label_key,
                    "icon": n.icon,
                    "section": n.section,
                    "order": n.order,
                    "perms": list(n.perms),
                    "group": n.group,
                    "parent": n.parent,
                }
                for n in self.nav
            ],
            "settings": [s.to_dict() for s in self.settings],
        }
