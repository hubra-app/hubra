"""Plugins.

``plugins_bp`` (platform managers, ``/api/v1/manager/plugins``): the marketplace, installing, updating,
rolling back and removing plugins, repositories and trusted signing keys.  Everything needs the global
permission ``plugins.manage``: a plugin is code that runs with full access.

``plugin_assets_bp`` (``/api/v1/plugins``): the built frontend of each
loaded plugin, which the club app loads at runtime.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import select

from hubra.core.auth.account_token import require_step_up
from hubra.core.permissions import require_global_permission
from hubra.core.errors import api_error, error_message
from hubra.core.extensions import db, limiter
from hubra.core.plugins import current
from hubra.core.plugins import installer
from hubra.core.plugins.installer import InstallError

plugins_bp = Blueprint("plugins_bp", __name__)
plugin_assets_bp = Blueprint("plugin_assets_bp", __name__)

_PERM = "plugins.manage"


def _error(exc: InstallError, status: int = 400):
    return api_error("PLUGIN_ERROR", error_message(exc), status)


def _repo_dict(r) -> dict:
    plugin_keys = installer.repository_plugin_keys(r)
    return {
        "id": r.id,
        "name": r.name,
        "url": r.url,
        "keyId": r.key_id,
        # False: the old format, its index key signs the plugins too.
        "separateKeys": bool(plugin_keys) and r.key_id not in plugin_keys,
        "pluginKeys": [
            {"name": n, "keyId": k} for k, (n, _p) in sorted(plugin_keys.items())
        ],
        "official": r.official,
        "enabled": r.enabled,
        "addedBy": r.added_by,
        "fetchedAt": r.fetched_at.isoformat() if r.fetched_at else None,
        "error": r.error,
    }


# ── Marketplace ──────────────────────────────────────────────────────────────


@plugins_bp.get("/")
@require_global_permission(_PERM)
def marketplace():
    """Every plugin: shipped, installed and offered by the repositories."""
    from hubra.core.plugins.updates import follow_dependencies, mode

    fetch = request.args.get("fetch", "1") != "0"
    data = installer.marketplace(fetch=fetch)
    data["updateMode"] = mode()
    data["updateDependencies"] = follow_dependencies()
    return jsonify(data), 200


@plugins_bp.get("/upgrade-impact")
@require_global_permission(_PERM)
def upgrade_impact():
    """``?version=0.3.0``: installed plugins that would stop loading on that
    Hubra version, whether an update fixes it, and how many clubs use them."""
    from hubra.core.plugins.impact import ImpactError, check

    try:
        return jsonify(check(request.args.get("version") or "")), 200
    except ImpactError as exc:
        return api_error("VALIDATION_ERROR", error_message(exc), 400)


@plugins_bp.post("/upload")
@require_global_permission(_PERM)
@require_step_up
def upload():
    """Check an uploaded .zip; answers what would be installed (confirm next)."""
    f = request.files.get("file")
    if f is None:
        return api_error("VALIDATION_ERROR", "send the plugin .zip as 'file'", 400)
    try:
        info = installer.stage(
            f.read(installer.MAX_ZIP + 1), source=f"upload {f.filename}"
        )
    except InstallError as exc:
        return _error(exc)
    return jsonify(info), 200


@plugins_bp.post("/stage/<string:token>/confirm")
@require_global_permission(_PERM)
@require_step_up
def confirm(token: str):
    body = request.get_json(silent=True) or {}
    try:
        out = installer.confirm(
            token,
            accept_unsigned=bool(body.get("acceptUnsigned")),
            repository_id=body.get("repositoryId"),
        )
    except InstallError as exc:
        return _error(exc)
    return jsonify(out), 200


@plugins_bp.delete("/stage/<string:token>")
@require_global_permission(_PERM)
def discard(token: str):
    installer.discard_stage(token)
    return "", 204


@plugins_bp.post("/<string:plugin_id>/install")
@require_global_permission(_PERM)
@require_step_up
def install(plugin_id: str):
    """Install or update *plugin_id*.

    A plugin that ships with Hubra installs at once (``installed``).  One
    from a repository is downloaded and checked first, and the answer is
    what would be installed (``staged``), to confirm.
    """
    from hubra.core.models.plugin import PluginRepository

    body = request.get_json(silent=True) or {}
    version = body.get("version")
    repo_id = body.get("repositoryId")
    spec = current().get(plugin_id)
    try:
        if repo_id is None and spec is not None and spec.bundled and not version:
            return jsonify({"installed": installer.install_bundled(plugin_id)}), 200
        if repo_id is None:
            return api_error("VALIDATION_ERROR", "repositoryId is required", 400)
        repo = db.session.get(PluginRepository, int(repo_id))
        if repo is None:
            return api_error("NOT_FOUND", "no such repository", 404)
        info = installer.install_from_repository(repo, plugin_id, version)
    except InstallError as exc:
        return _error(exc)
    return jsonify({"staged": info}), 200


@plugins_bp.post("/<string:plugin_id>/rollback")
@require_global_permission(_PERM)
@require_step_up
def rollback(plugin_id: str):
    try:
        return jsonify(installer.rollback(plugin_id)), 200
    except InstallError as exc:
        return _error(exc)


@plugins_bp.put("/<string:plugin_id>/hold")
@require_global_permission(_PERM)
def hold(plugin_id: str):
    body = request.get_json(silent=True) or {}
    try:
        installer.hold(plugin_id, body.get("version") or None)
    except InstallError as exc:
        return _error(exc)
    return jsonify({"held": body.get("version") or ""}), 200


@plugins_bp.delete("/<string:plugin_id>")
@require_global_permission(_PERM)
@require_step_up
def uninstall(plugin_id: str):
    delete_data = request.args.get("deleteData") in ("1", "true")
    try:
        return jsonify(installer.uninstall(plugin_id, delete_data=delete_data)), 200
    except InstallError as exc:
        return _error(exc)


@plugins_bp.get("/status")
@require_global_permission(_PERM)
def status():
    """What this process has loaded, to tell when a reload went through."""
    plugins = current()
    return jsonify(
        {
            "generation": plugins.generation,
            "loaded": {s.id: s.version for s in plugins.loaded()},
            "errors": {
                s.id: s.error
                for s in plugins.specs.values()
                if s.error and s.id in plugins.wanted
            },
        }
    ), 200


# ── Updates ──────────────────────────────────────────────────────────────────


@plugins_bp.put("/updates")
@require_global_permission(_PERM)
@require_step_up
def set_update_mode():
    from hubra.core.plugins.updates import (
        follow_dependencies,
        mode,
        set_follow_dependencies,
        set_mode,
    )

    body = request.get_json(silent=True) or {}
    if "mode" not in body and "dependencies" not in body:
        return api_error("VALIDATION_ERROR", "mode or dependencies is required", 400)
    if "mode" in body:
        try:
            set_mode(str(body.get("mode", "")))
        except ValueError as exc:
            return api_error("VALIDATION_ERROR", f"mode: {error_message(exc)}", 400)
    if "dependencies" in body:
        if not isinstance(body["dependencies"], bool):
            return api_error("VALIDATION_ERROR", "dependencies: true or false", 400)
        set_follow_dependencies(body["dependencies"])
    return jsonify({"mode": mode(), "dependencies": follow_dependencies()}), 200


@plugins_bp.post("/updates/check")
@require_global_permission(_PERM)
def check_updates():
    from hubra.core.plugins.updates import check

    return jsonify(check(force=True)), 200


# ── Repositories ─────────────────────────────────────────────────────────────


@plugins_bp.get("/repositories")
@require_global_permission(_PERM)
def list_repositories():
    from hubra.core.models.plugin import PluginRepository

    repos = db.session.scalars(
        select(PluginRepository).order_by(
            PluginRepository.official.desc(), PluginRepository.name
        )
    ).all()
    return jsonify([_repo_dict(r) for r in repos]), 200


@plugins_bp.post("/repositories/preview")
@require_global_permission(_PERM)
def preview_repository():
    """Fetch an index and show its name and key, before trusting it."""
    url = str((request.get_json(silent=True) or {}).get("url", "")).strip()
    try:
        return jsonify(installer.preview_repository(url)), 200
    except InstallError as exc:
        return _error(exc)


@plugins_bp.post("/repositories")
@require_global_permission(_PERM)
@require_step_up
def add_repository():
    """Add a repository; ``keyId`` is the key the manager compared."""
    body = request.get_json(silent=True) or {}
    url = str(body.get("url", "")).strip()
    key_id = str(body.get("keyId", "")).strip()
    if not url or not key_id:
        return api_error("VALIDATION_ERROR", "url and keyId are required", 400)
    try:
        repo = installer.add_repository(url, key_id)
    except InstallError as exc:
        return _error(exc)
    return jsonify(_repo_dict(repo)), 201


@plugins_bp.put("/repositories/<int:repo_id>")
@require_global_permission(_PERM)
@require_step_up
def update_repository(repo_id: int):
    from hubra.core.models.plugin import PluginRepository

    repo = db.session.get(PluginRepository, repo_id)
    if repo is None:
        return api_error("NOT_FOUND", "no such repository", 404)
    body = request.get_json(silent=True) or {}
    if isinstance(body.get("enabled"), bool):
        repo.enabled = body["enabled"]
    db.session.commit()
    return jsonify(_repo_dict(repo)), 200


@plugins_bp.delete("/repositories/<int:repo_id>")
@require_global_permission(_PERM)
@require_step_up
def delete_repository(repo_id: int):
    """Remove a repository.  Plugins installed from it stay installed."""
    from hubra.core.models.plugin import PluginRepository

    repo = db.session.get(PluginRepository, repo_id)
    if repo is None:
        return api_error("NOT_FOUND", "no such repository", 404)
    installer._audit("remove_plugin_repository", repo.name, {"url": repo.url})
    db.session.delete(repo)
    db.session.commit()
    return "", 204


# ── Trusted keys ─────────────────────────────────────────────────────────────


@plugins_bp.get("/keys")
@require_global_permission(_PERM)
def list_keys():
    """Every key this platform trusts, with its purpose: "plugins" (signs
    plugins), "index" (signs a repository index) or "both" (an index in the
    old format), and where it comes from (official, repository, manual)."""
    from hubra.core.models.plugin import PluginRepository, TrustedKey
    from hubra.core.plugins.trust import official_keys

    plugins, index = official_keys("plugins"), official_keys("index")
    keys = [
        {
            "id": None,
            "name": name,
            "keyId": kid,
            "purpose": "both" if kid in index else "plugins",
            "source": "official",
            "official": True,
        }
        for kid, (name, _pub) in plugins.items()
    ]
    keys += [
        {
            "id": None,
            "name": name,
            "keyId": kid,
            "purpose": "index",
            "source": "official",
            "official": True,
        }
        for kid, (name, _pub) in index.items()
        if kid not in plugins
    ]
    seen = {k["keyId"] for k in keys}
    for r in db.session.scalars(
        select(PluginRepository).where(PluginRepository.official.is_(False))
    ):
        pk = installer.repository_plugin_keys(r)
        rows = [(r.key_id, r.name, "both" if r.key_id in pk else "index")]
        rows += [
            (k, n, "plugins") for k, (n, _p) in sorted(pk.items()) if k != r.key_id
        ]
        for kid, name, purpose in rows:
            if kid in seen:
                continue
            seen.add(kid)
            keys.append(
                {
                    "id": None,
                    "name": name,
                    "keyId": kid,
                    "purpose": purpose,
                    "source": "repository",
                    "repository": r.name,
                    "official": False,
                }
            )
    keys += [
        {
            "id": k.id,
            "name": k.name,
            "keyId": k.key_id,
            "purpose": k.purpose,
            "source": "manual",
            "official": False,
            "addedBy": k.added_by,
        }
        for k in db.session.scalars(select(TrustedKey).order_by(TrustedKey.name))
    ]
    return jsonify(keys), 200


@plugins_bp.post("/keys")
@require_global_permission(_PERM)
@require_step_up
def add_key():
    """Trust an author's public key (their plugins then install as community)."""
    from hubra.core.models.plugin import TrustedKey
    from hubra.core.plugins.trust import key_id, load_public, public_b64

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()[:64]
    purpose = str(body.get("purpose") or "plugins")
    if purpose != "plugins":
        return api_error(
            "VALIDATION_ERROR",
            "only plugin keys can be added here; an index key comes with its repository",
            400,
        )
    try:
        pub = load_public(str(body.get("publicKey", "")))
    except (ValueError, TypeError):
        return api_error(
            "VALIDATION_ERROR", "publicKey: an Ed25519 public key (PEM)", 400
        )
    kid = key_id(pub)
    if not name:
        return api_error("VALIDATION_ERROR", "name is required", 400)
    if db.session.scalar(select(TrustedKey).where(TrustedKey.key_id == kid)):
        return api_error("CONFLICT", f"key {kid} is trusted already", 409)
    if kid in installer.index_key_ids():
        return api_error(
            "VALIDATION_ERROR",
            f"key {kid} signs a repository index; a key has one purpose, so it "
            "can't be trusted for plugins too",
            400,
        )
    key = TrustedKey(
        name=name,
        key_id=kid,
        public_key=public_b64(pub),
        purpose=purpose,
        added_by=installer._actor(),
    )
    db.session.add(key)
    installer._audit("trust_plugin_key", kid, {"name": name, "purpose": purpose})
    db.session.commit()
    return jsonify(
        {
            "id": key.id,
            "name": name,
            "keyId": kid,
            "purpose": purpose,
            "source": "manual",
            "official": False,
        }
    ), 201


@plugins_bp.delete("/keys/<int:key_pk>")
@require_global_permission(_PERM)
@require_step_up
def delete_key(key_pk: int):
    from hubra.core.models.plugin import TrustedKey

    key = db.session.get(TrustedKey, key_pk)
    if key is None:
        return api_error("NOT_FOUND", "no such key", 404)
    installer._audit("untrust_plugin_key", key.key_id, {"name": key.name})
    db.session.delete(key)
    db.session.commit()
    return "", 204


# ── Assets ───────────────────────────────────────────────────────────────────


@plugin_assets_bp.get("/<string:plugin_id>/frontend.js")
@limiter.exempt
def frontend(plugin_id: str):
    """The plugin's built frontend.  Only loaded plugins, only that one file."""
    spec = current().get(plugin_id)
    if spec is None or not spec.loaded or spec.frontend_file is None:
        return api_error("NOT_FOUND", "no frontend for this plugin", 404)
    resp = send_file(spec.frontend_file, mimetype="text/javascript", max_age=3600)
    # The app asks for ?v=<tag of the build it expects>.  A server that hasn't
    # reloaded after an update yet still has the old build: never let a cache
    # keep that under the new tag.
    wanted = request.args.get("v")
    if wanted and wanted != spec.frontend_tag:
        resp.headers["Cache-Control"] = "no-store"
    else:
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
