"""System service — diagnostic endpoints."""

from __future__ import annotations

from flask import current_app


class SystemService:
    """System-level introspection."""

    @staticmethod
    def list_permissions() -> list[dict]:
        """Return all permission-gated endpoints sorted by path and method."""
        from vollbuild.api.permissions import _derive_perm_key

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

        return sorted(entries, key=lambda e: (e["path"], e["method"]))
