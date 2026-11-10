"""Which clubs use which modules and plugins (manage › Plugins › Nutzung).

For every active club: the modules that are on (``modules.enabled_codes``)
and, per module, how many rows of its own tables (``Module.tables``) were
written in the last ``DAYS`` days, by the first timestamp column a table has
(``updated_at``, then ``created_at``, …). A module that is on in a club but
wrote nothing there counts as idle in that club.

Counting reads every club's schema, so it runs nightly
(``usage-snapshot-nightly``) and on "Jetzt berechnen" in manage; the last
result is kept in Redis (``KEY``) and read from there.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, func, select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

KEY = "usage:modules"
DAYS = 30
# Which column says a row was touched, in order of preference.
_STAMPS = (
    "updated_at",
    "created_at",
    "time",
    "sent_at",
    "submitted_at",
    "recorded_at",
    "starts_at",
)
# Clubs listed per module as idle (on, but nothing written).
_IDLE_LIST = 25


def _stamp_column(table_name: str):
    table = db.metadata.tables.get(table_name)
    if table is None:
        return None, None
    for name in _STAMPS:
        col = table.columns.get(name)
        if col is not None and isinstance(col.type, DateTime):
            return table, col
    return table, None


def _touched(code_tables: tuple[str, ...], since: datetime) -> int:
    """Rows written since *since* in these tables, in the current club."""
    total = 0
    for name in code_tables:
        table, col = _stamp_column(name)
        if table is None or col is None:
            continue
        try:
            total += int(
                db.session.scalar(
                    select(func.count()).select_from(table).where(col >= since)
                )
                or 0
            )
        except Exception:  # noqa: BLE001 - a table missing in an old club
            db.session.rollback()
            _log.debug("usage: %s not counted", name, exc_info=True)
    return total


def compute(days: int = DAYS) -> dict:
    """Count now (every club's schema). See the module docstring."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.modules import registry
    from hubra.core.modules.state import enabled_codes
    from hubra.core.tenant.context import in_club

    since = datetime.now(timezone.utc) - timedelta(days=days)
    modules = {m.code: m for m in registry.all()}
    clubs = db.session.scalars(
        select(Tenant).where(Tenant.status == "active").order_by(Tenant.name)
    ).all()

    per_module: dict[str, dict] = {
        code: {"on": 0, "active": 0, "rows": 0, "idle": []} for code in modules
    }
    plugin_clubs: dict[str, set[int]] = {}
    # Only tables with a timestamp say anything about use.
    measurable = {
        code: any(_stamp_column(t)[1] is not None for t in m.tables)
        for code, m in modules.items()
    }
    for club in clubs:
        try:
            on = set(enabled_codes(club.id))
        except Exception:  # noqa: BLE001
            _log.warning("usage: modules of club %s unknown", club.id, exc_info=True)
            continue
        with in_club(club):
            for code in on & set(modules):
                row = per_module[code]
                row["on"] += 1
                if modules[code].plugin:
                    plugin_clubs.setdefault(modules[code].plugin, set()).add(club.id)
                tables = modules[code].tables
                if not measurable[code]:
                    continue
                touched = _touched(tables, since)
                row["rows"] += touched
                if touched:
                    row["active"] += 1
                elif len(row["idle"]) < _IDLE_LIST:
                    row["idle"].append({"id": club.id, "name": club.name})

    plugins = _plugins()
    for pid, plugin in plugins.items():
        plugin["clubsOn"] = len(plugin_clubs.get(pid, set()))
    rows = []
    for code, m in sorted(modules.items(), key=lambda kv: kv[1].name.lower()):
        counts = per_module[code]
        plugin = plugins.get(m.plugin or "")
        rows.append(
            {
                "code": code,
                "name": m.name,
                "required": bool(m.required),
                "plugin": m.plugin,
                "pluginName": plugin["name"] if plugin else None,
                "version": plugin["version"] if plugin else None,
                # Without timestamped tables of its own, use can't be counted.
                "measured": measurable[code],
                "clubsOn": counts["on"],
                "clubsActive": counts["active"],
                "clubsIdle": counts["on"] - counts["active"]
                if measurable[code]
                else None,
                "rows": counts["rows"],
                "idle": counts["idle"],
            }
        )
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "clubs": len(clubs),
        "modules": rows,
        "plugins": sorted(plugins.values(), key=lambda p: p["name"].lower()),
    }


def _plugins() -> dict[str, dict]:
    """Installed plugins with their version and modules."""
    try:
        from hubra.core.plugins import loader

        loaded = loader.current().loaded()
    except Exception:  # noqa: BLE001
        return {}
    return {
        spec.id: {
            "id": spec.id,
            "name": spec.name or spec.id,
            "version": spec.version,
            "modules": list(spec.module_codes),
        }
        for spec in loaded
    }


def refresh() -> dict:
    """Count and keep the result."""
    from hubra.core.services import platform_bot

    data = compute()
    platform_bot._set(KEY, json.dumps(data))
    return data


def latest() -> dict | None:
    """The last kept result, or None before the first count."""
    from hubra.core.services import platform_bot

    raw = platform_bot._get(KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
