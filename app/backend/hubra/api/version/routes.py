"""Version blueprint: app version, changelog, roadmap and instance info (public, no auth)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from hubra.core.services.version import VersionService

version_bp = Blueprint("version_bp", __name__)


@version_bp.get("/version")
def get_version():
    """Return the current backend version and the commit it was built from."""
    from hubra.core.build_info import commit

    return jsonify({"version": VersionService.get_version(), "commit": commit()}), 200


@version_bp.get("/version/changelog")
def get_changelog():
    """The backend version and the changelog entries; ``?lang=de`` for German.

    The club app asks for one reader: ``?modules=events,posts`` (the modules
    the club has and the reader may use) and ``admin=1`` leave out the items
    marked for other modules, for admins or for Hubra's team
    (``<!-- for: ... -->`` in CHANGELOG.md, see docs/releases.md).
    """
    entries = VersionService.get_changelog(request.args.get("lang"))
    if "modules" in request.args:
        modules = {
            m.strip().lower()
            for m in request.args.get("modules", "").split(",")
            if m.strip()
        }
        entries = VersionService.for_reader(
            entries, modules, admin=request.args.get("admin") == "1"
        )
    return (
        jsonify(
            {
                "version": VersionService.get_version(),
                "entries": [
                    {k: v for k, v in e.items() if k != "tags"} for e in entries
                ],
            }
        ),
        200,
    )


@version_bp.get("/version/roadmap")
def get_roadmap():
    """The one public roadmap: what is being built now, next, later, what
    shipped, and the ideas people vote on (ROADMAP.yaml plus the ideas staff
    put on it; same as ``/roadmap``)."""
    from hubra.core.services import support

    return jsonify(support.roadmap()), 200


@version_bp.get("/instance")
def get_instance():
    """Tell the SPAs where the SSO portal is and where Hubra's legal pages
    are (platform settings ``legal.*``), before anyone signs in."""
    from hubra.core.services import platform_settings

    sso = current_app.config.get("SSO_BASE_URL", "")
    return (
        jsonify(
            {
                "ssoUrl": str(sso).rstrip("/") or None,
                "legal": platform_settings.legal_links(),
            }
        ),
        200,
    )
