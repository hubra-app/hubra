"""Upgrade impact: which installed plugins stop loading on another Hubra
version, and which clubs use them.

Every plugin names the Hubra versions it works with (``hubra:`` in
plugin.yaml, a PEP 440 range).  Before a core upgrade, manage asks
:func:`check` with the version to move to; for each installed plugin it
answers whether the installed version takes it, and if not, whether a version
in the repositories does (update the plugin first) or none does (wait for the
plugin, or the clubs that use it lose it).  The release workflow runs the same
check against the official index (``scripts/release_check.py plugins``).
"""

from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from sqlalchemy import func, select

from hubra.core.extensions import db

OK = "ok"
UPDATE = "update"  # a repository version takes the target: update first
BLOCKED = "blocked"  # no known version takes it


class ImpactError(ValueError):
    pass


def _takes(spec: str, target: Version) -> bool:
    if not spec:
        return True
    try:
        return SpecifierSet(spec).contains(target, prereleases=True)
    except InvalidSpecifier:
        return False


def _clubs_using(modules: list[str]) -> int:
    from hubra.core.models.feature import TenantFeature

    if not modules:
        return 0
    return int(
        db.session.scalar(
            select(func.count(func.distinct(TenantFeature.tenant_id))).where(
                TenantFeature.feature_code.in_(modules), TenantFeature.enabled.is_(True)
            )
        )
        or 0
    )


def check(target: str | None) -> dict:
    """``{"target", "current", "plugins": [...], "counts": {...}}``; each
    plugin row has ``state`` ok / update / blocked, its installed range, the
    version to update to and how many clubs use it."""
    from hubra.core.plugins import current
    from hubra.core.plugins.installer import marketplace
    from hubra.core.plugins.spec import hubra_version

    if not str(target or "").strip():
        # The usual next release: the next minor version of what runs now.
        now = Version(hubra_version())
        target = f"{now.major}.{now.minor + 1}.0"
    try:
        version = Version(str(target).strip().lstrip("v"))
    except InvalidVersion as exc:
        raise ImpactError(f"'{target}' is not a version like 0.3.0") from exc

    loaded = current()
    rows = []
    for entry in marketplace(fetch=False)["plugins"]:
        if not entry.get("installed"):
            continue
        have = str(entry.get("installedVersion") or entry.get("version") or "")
        spec = loaded.get(entry["id"])
        installed_range = ""
        if spec is not None and spec.manifest:
            installed_range = str(spec.manifest.get("hubra") or "")
        else:
            mine = next(
                (v for v in entry.get("versions") or [] if v.get("version") == have),
                None,
            )
            installed_range = str((mine or {}).get("hubra") or "")
        candidates = [
            v
            for v in entry.get("versions") or []
            if not v.get("yanked") and _takes(str(v.get("hubra") or ""), version)
        ]
        if _takes(installed_range, version):
            state, to = OK, None
        elif candidates:
            state, to = UPDATE, str(candidates[0]["version"])
        else:
            state, to = BLOCKED, None
        modules = [str(m) for m in entry.get("modules") or []]
        rows.append(
            {
                "id": entry["id"],
                "name": entry.get("name") or entry["id"],
                "installedVersion": have,
                "requiresHubra": installed_range,
                "state": state,
                "updateTo": to,
                "clubs": _clubs_using(modules) if state != OK else None,
            }
        )
    order = {BLOCKED: 0, UPDATE: 1, OK: 2}
    rows.sort(key=lambda r: (order[r["state"]], str(r["name"]).lower()))
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in (OK, UPDATE, BLOCKED)}
    return {
        "target": str(version),
        "current": hubra_version(),
        "plugins": rows,
        "counts": counts,
    }
