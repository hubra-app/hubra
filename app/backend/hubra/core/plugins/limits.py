"""What a plugin may extend, checked when it loads (docs/plugins.md).

Plugins are club features. They act only in the club area of the API and
on the club's queue; manage, the platform API and the global API (sign-in,
account) are out of reach. :func:`check` runs on every module manifest a
plugin declares, before the module joins the registry, and either returns
the manifest to register (route prefixes moved into the club area) or
raises :class:`LimitError` with what is wrong.

The checks:

- Everything a manifest points at (blueprints, event handlers, Celery task
  modules, scheduled tasks, processes, connected-app handlers) lives in the
  plugin's own package, so a plugin can't register one of Hubra's own
  blueprints or tasks under another name.
- Route prefixes lie in the club area, ``/api/v1/app/...``. A prefix in the
  old form, ``/api/v1/<name>``, is moved there and the old path keeps
  working (``api_areas.add_plugin_prefix``). The platform and global areas
  are refused, and so is a prefix that Hubra or another plugin already uses.
  An official plugin may add routes below the prefix of a module it depends
  on (a bookkeeping plugin under ``/api/v1/app/finance``) and keep that
  module's permission keys with ``perm_prefix``.
- Tables are the plugin's own: none of Hubra's tenant tables.
- Processes and in-transaction event handlers are for official plugins
  (signed with Hubra's key, or shipped with Hubra) only.
- Contracts (``provides``) are named after the module (``<code>.<what>``),
  their handlers and schemas are the plugin's own code, and ``consumes``
  gives a version range for each contract it uses (docs/contracts.md).
- A plugin that lists ``uses:`` in plugin.yaml touches only the areas it
  listed. A plugin without the list still loads (plugins released before
  it existed) and the catalogue shows it as undeclared.
"""

from __future__ import annotations

import dataclasses
import logging

from hubra.core.api_areas import APP, GLOBAL, PLATFORM, V1, canonical_path

_log = logging.getLogger(__name__)

# Trust levels whose plugins may run processes and in-transaction handlers.
OFFICIAL = ("official", "bundled")


class LimitError(ValueError):
    pass


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def _own(target: str, pkg: str) -> bool:
    """Whether a dotted path (``a.b:c`` or ``a.b.c``) is inside package *pkg*."""
    mod = target.partition(":")[0]
    return mod == pkg or mod.startswith(pkg + ".")


def areas_used(module, spec) -> set[str]:
    """The extension areas a module manifest (and its plugin) touch."""
    used = set()
    if module.blueprints:
        used.add("routes")
    if module.public_endpoints:
        used.add("public")
    if module.events:
        used.add("events")
    if module.tasks or module.schedule:
        used.add("jobs")
    if module.processes:
        used.add("processes")
    if module.tables or spec.migrations_dir is not None:
        used.add("tables")
    if module.settings:
        used.add("settings")
    if module.apps:
        used.add("apps")
    if module.nav:
        used.add("nav")
    if module.provides or module.consumes:
        used.add("contracts")
    if spec.frontend_file is not None:
        used.add("frontend")
    return used


def club_prefix(prefix: str) -> str:
    """The club-area prefix a plugin route is served under.

    ``/api/v1/app/bank`` stays; ``/api/v1/bank`` (the form plugins used
    before the API areas) becomes ``/api/v1/app/bank``. Raises LimitError
    for anything outside the club area.
    """
    raw = "/" + str(prefix or "").strip().strip("/")
    if not _under(raw, V1) or raw == V1:
        raise LimitError(f"route prefix {prefix!r} must start with {V1}/")
    new = canonical_path(raw)
    if _under(new, PLATFORM) or _under(new, GLOBAL):
        raise LimitError(
            f"route prefix {prefix!r} is in the {'platform' if _under(new, PLATFORM) else 'global'}"
            " area; plugins may only add club routes under /api/v1/app/"
        )
    if _under(new, APP):
        if new == APP:
            raise LimitError("route prefix /api/v1/app needs a name after it")
        return new
    return APP + new[len(V1) :]


# Contracts every module offers in the same shape (the club calendar, search,
# privacy export): a plugin's input and output may be Hubra's models there;
# the handler is still its own code.
SHARED_SHAPES = (
    "hubra.core.contracts.calendar",
    "hubra.core.contracts.privacy",
    "hubra.core.contracts.search",
)


def _shared_shape(ref: str, handler: str | None) -> bool:
    return ref != handler and ref.split(":", 1)[0] in SHARED_SHAPES


def check(module, spec, taken_prefixes: dict[str, str], core_tables: set[str]):
    """Return *module* ready to register, or raise LimitError.

    *taken_prefixes* maps the club-area route prefixes already registered to
    their module code; it is updated with this module's. *core_tables* are
    the tenant tables of Hubra's own modules.
    """
    pkg = spec.package or ""
    official = spec.trust.get("status") in OFFICIAL

    # 1. Everything it points at is its own code.
    targets = [bp.import_path for bp in module.blueprints]
    targets += list(module.events.values())
    targets += list(module.tasks)
    targets += [s.task for s in module.schedule]
    targets += list(module.processes.values())
    targets += [a.handler for a in module.apps]
    foreign = sorted({t for t in targets if not _own(t, pkg)})
    if foreign:
        raise LimitError(
            f"module {module.code} points at code outside {pkg}: {', '.join(foreign)}"
        )

    # 2. Routes in the club area, nobody else's prefix.
    blueprints = []
    for bp in module.blueprints:
        new = club_prefix(bp.url_prefix)
        for other, owner in taken_prefixes.items():
            # A blueprint on a bare area root (/api/v1/app) or on the site
            # root (the OAuth /.well-known metadata) holds a few routes of its
            # own; it doesn't own everything below it.
            if owner == module.code or other in ("/", V1, APP, GLOBAL, PLATFORM):
                continue
            if official and owner in module.depends_on and _under(new, other):
                continue  # extends a module it depends on; Flask matches by rule
            if _under(new, other) or _under(other, new):
                raise LimitError(
                    f"route prefix {bp.url_prefix!r} overlaps {other} of {owner}"
                )
        if (
            bp.perm_prefix
            and bp.perm_prefix != module.code
            and (not official or bp.perm_prefix not in module.depends_on)
        ):
            raise LimitError(
                f"module {module.code} may only use the permission keys of a"
                f" module it depends on, not {bp.perm_prefix!r}"
                + ("" if official else " (official plugins only)")
            )
        taken_prefixes.setdefault(new, module.code)
        blueprints.append(dataclasses.replace(bp, url_prefix=new))

    # 3. Own tables only.
    clash = sorted(set(module.tables) & core_tables)
    if clash:
        raise LimitError(
            f"module {module.code} claims Hubra's table(s) {', '.join(clash)}"
        )

    # 4. Official plugins only: processes and in-transaction handlers.
    if module.processes and not official:
        raise LimitError(
            f"module {module.code} runs a process; only official plugins may"
        )
    in_tx = tuple(module.events_in_transaction)
    if in_tx and not official:
        _log.warning(
            "Plugin %s: events_in_transaction ignored (not an official plugin); "
            "its handlers run after the commit",
            spec.id,
        )
        in_tx = ()

    # 5. Contracts: its own names and code, version ranges that parse.
    _check_contracts(module, pkg)

    # 6. Only the areas it declared.
    declared = spec.uses
    if declared is not None:
        extra = sorted(areas_used(module, spec) - set(declared))
        if extra:
            raise LimitError(
                f"module {module.code} uses {', '.join(extra)}, "
                "which plugin.yaml doesn't list under uses:"
            )

    return dataclasses.replace(
        module, blueprints=tuple(blueprints), events_in_transaction=in_tx
    )


def _check_contracts(module, pkg: str) -> None:
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    from hubra.core.contracts.base import Contract
    from hubra.core.contracts.core_events import CORE_EVENTS

    core = {c.name for c in CORE_EVENTS}
    seen: set[str] = set()
    for c in module.provides:
        if not isinstance(c, Contract):
            raise LimitError(f"module {module.code}: provides lists {c!r}, not a Contract")
        if not c.name.startswith(module.code + "."):
            raise LimitError(
                f"module {module.code} offers {c.name}; its contracts are named"
                f" {module.code}.<what>"
            )
        if c.name in core or c.name in seen:
            raise LimitError(f"module {module.code} offers {c.name} twice or Hubra's own")
        seen.add(c.name)
        refs = [c.handler] if c.handler else []
        for schema in (c.input, c.output):
            if isinstance(schema, str):
                refs.append(schema)
            elif schema is not None:
                refs.append(f"{getattr(schema, '__module__', '')}:{getattr(schema, '__name__', '')}")
        foreign = sorted(
            {r for r in refs if not _own(r, pkg) and not _shared_shape(r, c.handler)}
        )
        if foreign:
            raise LimitError(
                f"contract {c.name} points at code outside {pkg}: {', '.join(foreign)}"
            )
    for name, rng in (module.consumes or {}).items():
        if not isinstance(name, str) or "." not in name:
            raise LimitError(f"module {module.code}: consumes names {name!r}")
        if rng in (None, ""):
            continue
        try:
            SpecifierSet(str(rng))
        except InvalidSpecifier:
            raise LimitError(
                f"module {module.code}: consumes {name}: {rng!r} isn't a range like '>=1,<2'"
            ) from None
