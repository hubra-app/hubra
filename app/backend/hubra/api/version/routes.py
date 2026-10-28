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
    """Tell the SPAs where the SSO portal is, before anyone signs in."""
    sso = current_app.config.get("SSO_BASE_URL", "")
    return jsonify({"ssoUrl": str(sso).rstrip("/") or None}), 200
