"""System service — diagnostic endpoints."""

from __future__ import annotations

from flask import current_app


class SystemService:
    """System-level introspection."""

    @staticmethod
    def list_permissions() -> list[dict]:
        """Return all permission-gated endpoints sorted by path and method."""
        from hubra.core.permissions import _derive_perm_key

        entries = []
        for rule in current_app.url_map.iter_rules():
            fn = current_app.view_functions.get(rule.endpoint)
            if fn is None:
                continue

            # New-style @permission_required metadata
            resource = getattr(fn, "_perm_resource", None)
            action = getattr(fn, "_perm_action", None)
            if resource is not None and action is not None:
                bp_name = (
                    rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
                )
                key = _derive_perm_key(bp_name, resource, action)
                display_name = getattr(fn, "_perm_display_name", f"{action} {resource}")
                methods = rule.methods or set()
                for method in sorted(methods - {"HEAD", "OPTIONS"}):
                    entries.append(
                        {
                            "method": method,
                            "path": rule.rule,
                            "key": key,
                            "display_name": display_name,
                            "resource": resource,
                            "action": action,
                            "blueprint": bp_name or "",
                        }
                    )

        from hubra.core.plugins.loader import loads_plugin_code

        if not loads_plugin_code():
            entries.extend(SystemService._catalog_only(entries))
        return sorted(entries, key=lambda e: (e["path"], e["method"]))

    @staticmethod
    def _catalog_only(entries: list[dict]) -> list[dict]:
        """Route permissions in the catalog whose routes aren't loaded here.

        The global and platform backends don't import plugin routes
        (``loader.MANIFEST_ONLY_ROLES``), so their permissions come from the
        catalog that ``flask sync-permissions`` filled, without path and
        method.
        """
        from sqlalchemy import select

        from hubra.core.extensions import db
        from hubra.core.fields import iter_field_perms
        from hubra.core.models.role import Permission
        from hubra.core.permissions import extra_permissions

        known = {e["key"] for e in entries}
        known.update(m["key"] for m in iter_field_perms())
        known.update(m["key"] for m in extra_permissions())
        rows = db.session.scalars(
            select(Permission).where(Permission.is_active.is_(True))
        ).all()
        return [
            {
                "method": "",
                "path": "",
                "key": p.key,
                "display_name": p.display_name,
                "resource": p.resource,
                "action": p.action,
                "blueprint": p.blueprint,
            }
            for p in rows
            if p.key not in known
        ]
