"""Version blueprint — app version, changelog and instance info (public, no auth)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from hubra.api.version.services import VersionService

version_bp = Blueprint("version_bp", __name__)


@version_bp.get("/version")
def get_version():
    """Return the current backend version."""
    return jsonify({"version": VersionService.get_version()}), 200


@version_bp.get("/version/changelog")
def get_changelog():
    """Return the current backend version plus structured changelog entries."""
    return (
        jsonify(
            {
                "version": VersionService.get_version(),
                "entries": VersionService.get_changelog(),
            }
        ),
        200,
    )


@version_bp.get("/instance")
def get_instance():
    """Tell the SPAs how this install is set up, before anyone signs in.

    ``mode`` is ``single`` when the install serves one club (SINGLE_CLUB):
    the club app then uses its own sign-in pages and there is no SSO or
    manager portal. ``ssoUrl`` is only set in multi-club mode.
    """
    from hubra.core.tenant.context import current_tenant, single_club_slug

    if single_club_slug():
        tenant = current_tenant()
        return jsonify(
            {
                "mode": "single",
                "club": (
                    {"slug": tenant.slug, "name": tenant.name} if tenant else None
                ),
                "ssoUrl": None,
                "signup": False,
            }
        ), 200
    sso = current_app.config.get("SSO_BASE_URL", "")
    return jsonify(
        {
            "mode": "multi",
            "club": None,
            "ssoUrl": str(sso).rstrip("/") or None,
            "signup": True,
        }
    ), 200
