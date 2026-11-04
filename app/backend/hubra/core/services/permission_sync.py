"""The permission catalog (``public.permissions``).

Every ``@permission_required`` route, every field permission and the
extra permissions (``EXTRA_PERMISSIONS`` and those of loaded modules) make one Permission row. ``flask sync-permissions``
runs this on every deploy; provisioning a club on an empty catalog runs it
too, because a club's roles can only grant permissions that exist.
"""

from __future__ import annotations

from flask import Flask
from sqlalchemy import select

from hubra.core.extensions import db


def sync_permission_catalog(app: Flask, *, commit: bool = True) -> tuple[int, int, int]:
    """Create, update and deactivate Permission rows to match the code.

    Returns ``(created, updated, orphaned)``. Commits unless ``commit`` is
    false (then the rows are flushed into the caller's transaction).
    """
    from hubra.core.fields import iter_field_perms
    from hubra.core.permissions import _derive_perm_key, extra_permissions
    from hubra.core.models.role import Permission

    discovered: dict[str, dict] = {}
    for rule in app.url_map.iter_rules():
        fn = app.view_functions.get(rule.endpoint)
        if fn is None:
            continue
        resource = getattr(fn, "_perm_resource", None)
        action = getattr(fn, "_perm_action", None)
        if resource is None or action is None:
            continue
        bp_name = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
        key = _derive_perm_key(bp_name, resource, action)
        display_name = getattr(fn, "_perm_display_name", f"{action} {resource}")
        discovered[key] = {
            "key": key,
            "display_name": display_name,
            "resource": resource,
            "action": action,
            "blueprint": bp_name or "",
        }

    existing = {p.key: p for p in db.session.scalars(select(Permission)).all()}

    # Field-level and extra permissions count as discovered too, so they are
    # never marked as orphaned.
    for meta in iter_field_perms():
        discovered[meta["key"]] = meta
    for meta in extra_permissions():
        discovered[meta["key"]] = meta

    created = 0
    updated = 0
    orphaned = 0

    for key, meta in discovered.items():
        perm = existing.get(key)
        if perm is None:
            db.session.add(
                Permission(
                    key=meta["key"],
                    display_name=meta["display_name"],
                    resource=meta["resource"],
                    action=meta["action"],
                    blueprint=meta["blueprint"],
                    is_active=True,
                )
            )
            created += 1
            continue
        changed = False
        for attr in ("display_name", "resource", "action", "blueprint"):
            if getattr(perm, attr) != meta[attr]:
                setattr(perm, attr, meta[attr])
                changed = True
        if not perm.is_active:
            perm.is_active = True
            changed = True
        if changed:
            updated += 1

    for key, perm in existing.items():
        if key not in discovered and perm.is_active:
            perm.is_active = False
            orphaned += 1

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return created, updated, orphaned
