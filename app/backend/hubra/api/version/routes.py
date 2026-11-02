"""Version blueprint: app version, changelog, roadmap and instance info (public, no auth)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from hubra.api.version.services import ROADMAP_STATUSES, VersionService

version_bp = Blueprint("version_bp", __name__)


@version_bp.get("/version")
def get_version():
    """Return the current backend version and the commit it was built from."""
    from hubra.core.build_info import commit

    return jsonify({"version": VersionService.get_version(), "commit": commit()}), 200


@version_bp.get("/version/changelog")
def get_changelog():
    """The backend version and the changelog entries; ``?lang=de`` for German."""
    return (
        jsonify(
            {
                "version": VersionService.get_version(),
                "entries": VersionService.get_changelog(request.args.get("lang")),
            }
        ),
        200,
    )


@version_bp.get("/version/roadmap")
def get_roadmap():
    """Return the roadmap: what is being built now, next, later, and what shipped."""
    return (
        jsonify(
            {"statuses": list(ROADMAP_STATUSES), "items": VersionService.get_roadmap()}
        ),
        200,
    )


@version_bp.get("/instance")
def get_instance():
    """Tell the SPAs where the SSO portal is, before anyone signs in."""
    sso = current_app.config.get("SSO_BASE_URL", "")
    return jsonify({"ssoUrl": str(sso).rstrip("/") or None}), 200
