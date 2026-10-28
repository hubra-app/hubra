"""Plugin updates: the update policy and the regular check (ported from labdex).

``plugin_state`` keys:
    update_mode    "notify" (default): announce updates, install nothing
                   "official": install updates signed with the Hubra project key
                               by themselves; announce the rest
                   "off": no check (the Marketplace still shows updates)
    updates_seen   {"plugin id": "version"}: what was announced already

A held plugin (``installed_plugins.held_version``) is never offered an
update.  Announcements go to the global audit log, which the manager portal
shows; the Marketplace badge comes from the same check.
"""

from __future__ import annotations

import json
import logging

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

MODES = ("notify", "official", "off")


def _get(key: str, default: str = "") -> str:
    from hubra.core.models.plugin import PluginState

    row = db.session.get(PluginState, key)
    return row.value if row is not None and row.value else default


def _put(key: str, value: str) -> None:
    from hubra.core.models.plugin import PluginState

    row = db.session.get(PluginState, key)
    if row is None:
        db.session.add(PluginState(key=key, value=value))
    else:
        row.value = value


def mode() -> str:
    m = _get("update_mode", "notify")
    return m if m in MODES else "notify"


def set_mode(m: str) -> None:
    if m not in MODES:
        raise ValueError(f"one of {', '.join(MODES)}")
    _put("update_mode", m)
    db.session.commit()


def check(force: bool = False) -> dict:
    """Announce what's new; in "official" mode install official updates."""
    from hubra.core.models.plugin import PluginRepository

    from .installer import (
        InstallError,
        _audit,
        confirm,
        install_from_repository,
        marketplace,
    )

    md = mode()
    if md == "off" and not force:
        return {"mode": md, "skipped": True}
    market = marketplace(fetch=True)
    try:
        seen = json.loads(_get("updates_seen", "{}"))
    except ValueError:
        seen = {}
    done = {"mode": md, "announced": [], "installed": [], "failed": [], "withdrawn": []}
    for p in market["plugins"]:
        if p.get("installed") and p.get("withdrawn"):
            key = f"withdrawn:{p['id']}"
            if seen.get(key) != p["installedVersion"]:
                seen[key] = p["installedVersion"]
                done["withdrawn"].append(p["id"])
                _audit(
                    "plugin_withdrawn",
                    p["id"],
                    {"version": p["installedVersion"], "reason": p["withdrawn"]},
                )
        if not p.get("update"):
            continue
        target = p["repoVersion"]
        if md == "official" and p.get("officialSigned") and p.get("repositoryId"):
            try:
                repo = db.session.get(PluginRepository, p["repositoryId"])
                info = install_from_repository(repo, p["id"], target)
                if info["trust"]["status"] != "official":
                    raise InstallError("not signed with the Hubra project key")
                confirm(info["token"], accept_unsigned=False, repository_id=repo.id)
                done["installed"].append(p["id"])
                seen[p["id"]] = target
                continue
            except Exception as exc:  # one plugin failing must not stop the others
                db.session.rollback()
                _log.warning("updating %s failed: %s", p["id"], exc)
                done["failed"].append(p["id"])
                _audit(
                    "plugin_update_failed",
                    p["id"],
                    {"version": target, "error": str(exc)[:500]},
                )
        if seen.get(p["id"]) != target:
            seen[p["id"]] = target
            done["announced"].append(p["id"])
            _audit("plugin_update_available", p["id"], {"version": target})
    _put("updates_seen", json.dumps(seen, sort_keys=True))
    db.session.commit()
    return done
