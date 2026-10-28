"""Version blueprint — exposes app version and changelog (public, no auth)."""

from __future__ import annotations

from flask import Blueprint, jsonify

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
