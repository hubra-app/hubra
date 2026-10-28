"""``flask plugins``: install and manage plugins, and publish them.

Platform::

    flask plugins list
    flask plugins sync                     # run on deploy, after flask db upgrade
    flask plugins install keys             # shipped with Hubra, or from a repository
    flask plugins install ./keys-1.0.0.zip [--accept-unsigned]
    flask plugins uninstall keys [--delete-data]
    flask plugins rollback keys
    flask plugins repo-add <index url>
    flask plugins check-updates

Authors and publishers::

    flask plugins keygen my.pem
    flask plugins sign ./keys --key my.pem --signer "Your Name"
    flask plugins pack ./keys -o keys-1.0.0.zip
    flask plugins repo ../../plugins ./public --key my.pem --name "My plugins"
    flask plugins build-index sources.yaml ./public --key my.pem
    flask plugins yank ./public keys 1.0.1 --key my.pem --reason "..."
    flask plugins revision keys -m "add a column" --autogenerate
"""

from __future__ import annotations

import os
from pathlib import Path

import click
from sqlalchemy import select


def register(app) -> None:
    from hubra.core.extensions import db

    @app.cli.group("plugins")
    def plugins_cli():
        """Install, remove and publish plugins."""

    def _fail(exc: Exception):
        raise click.ClickException(str(exc)) from exc

    @plugins_cli.command("list")
    def plugins_list():
        """Every plugin this process sees, and whether it is installed and loaded."""
        from .installer import marketplace

        for p in marketplace(fetch=False)["plugins"]:
            state = (
                "loaded   "
                if p.get("loaded")
                else ("installed" if p.get("installed") else "available")
            )
            note = f"  ! {p['error']}" if p.get("error") else ""
            trust = (p.get("trust") or {}).get("status", "")
            click.echo(
                f"{state} {p['id']:<16} {p.get('version', ''):<10} {trust:<9}{note}"
            )

    @plugins_cli.command("sync")
    def plugins_sync():
        """Bring every installed plugin's tables up to date (public and every club).

        Run after ``flask db upgrade`` on every deploy.  Also seeds the
        official repository once.
        """
        from . import current, migrate
        from .installer import cleanup_archives, ensure_official_repository

        ensure_official_repository()
        for spec in current().loaded():
            migrate.upgrade_everywhere(spec)
            click.echo(f"{spec.id} {spec.version}: migrated")
        problems = [
            s for s in current().specs.values() if s.error and s.id in current().wanted
        ]
        for spec in problems:
            click.echo(f"{spec.id}: not loaded: {spec.error}", err=True)
        cleanup_archives()
        db.session.commit()

    @plugins_cli.command("install")
    @click.argument("what")
    @click.option("--version", default=None, help="A version from the repository.")
    @click.option(
        "--repository",
        default=None,
        help="The repository's name (default: the first that has it).",
    )
    @click.option(
        "--accept-unsigned", is_flag=True, help="Install an unsigned archive."
    )
    def plugins_install(what, version, repository, accept_unsigned):
        """Install WHAT: a plugin id, or the path of a plugin .zip."""
        from hubra.core.models.plugin import PluginRepository

        from . import current
        from .installer import (
            InstallError,
            confirm,
            fetch_repository,
            install_bundled,
            install_from_repository,
            stage,
        )

        try:
            if what.endswith(".zip") and Path(what).is_file():
                info = stage(Path(what).read_bytes(), source=f"file {what}")
                click.echo(
                    f"{info['name']} {info['version']}: {info['trust']['detail'] or info['trust']['status']}"
                )
                out = confirm(info["token"], accept_unsigned)
            elif (
                current().get(what) is not None
                and current().get(what).bundled
                and not (version or repository)
            ):
                out = install_bundled(what)
            else:
                repos = db.session.scalars(
                    select(PluginRepository).where(PluginRepository.enabled.is_(True))
                ).all()
                if repository:
                    repos = [r for r in repos if r.name == repository]
                repo = next(
                    (
                        r
                        for r in repos
                        if any(
                            str(p.get("id")) == what
                            for p in fetch_repository(r)["plugins"]
                        )
                    ),
                    None,
                )
                if repo is None:
                    raise InstallError(f"no repository offers '{what}'")
                info = install_from_repository(repo, what, version)
                out = confirm(info["token"], accept_unsigned, repository_id=repo.id)
        except InstallError as exc:
            _fail(exc)
        click.echo(
            f"Installed {out['id']} {out['version']}. Running processes reload within a minute."
        )

    @plugins_cli.command("uninstall")
    @click.argument("plugin_id")
    @click.option(
        "--delete-data", is_flag=True, help="Also drop its tables in every club."
    )
    def plugins_uninstall(plugin_id, delete_data):
        from .installer import InstallError, uninstall

        try:
            out = uninstall(plugin_id, delete_data=delete_data)
        except InstallError as exc:
            _fail(exc)
        click.echo(
            f"Removed {out['id']} {out['version']}{' and its data' if delete_data else ''}."
        )

    @plugins_cli.command("rollback")
    @click.argument("plugin_id")
    def plugins_rollback(plugin_id):
        """Go back to the version the last update replaced."""
        from .installer import InstallError, rollback

        try:
            out = rollback(plugin_id)
        except InstallError as exc:
            _fail(exc)
        click.echo(f"{out['id']}: {out['previous']} -> {out['version']}")

    @plugins_cli.command("repo-add")
    @click.argument("url")
    @click.option(
        "--key-id",
        default=None,
        help="The key id the publisher gave you (asked otherwise).",
    )
    def plugins_repo_add(url, key_id):
        """Add a signed repository; its key is pinned from then on."""
        from .installer import InstallError, add_repository, preview_repository

        try:
            info = preview_repository(url)
            click.echo(
                f"{info['name']}: {info['plugins']} plugin(s), key {info['keyId']}"
            )
            if key_id is None:
                click.confirm("Is this the key id the publisher gave you?", abort=True)
                key_id = info["keyId"]
            repo = add_repository(url, key_id)
        except InstallError as exc:
            _fail(exc)
        click.echo(f"Added {repo.name}.")

    @plugins_cli.command("check-updates")
    def plugins_check_updates():
        from .updates import check

        click.echo(check(force=True))

    @plugins_cli.command("revision")
    @click.argument("plugin_id")
    @click.option("-m", "--message", required=True)
    @click.option("--autogenerate", is_flag=True)
    def plugins_revision(plugin_id, message, autogenerate):
        """Write a new migration into a loaded plugin's migrations folder."""
        from . import current, migrate

        spec = current().get(plugin_id)
        if spec is None or not spec.loaded:
            raise click.ClickException(
                f"{plugin_id} isn't loaded; set HUBRA_PLUGINS_AUTOINSTALL={plugin_id} for development"
            )
        try:
            migrate.revision(spec, message, autogenerate)
        except ValueError as exc:
            _fail(exc)

    # ── Publishing ───────────────────────────────────────────────────────────

    @plugins_cli.command("keygen")
    @click.argument("private_key", type=click.Path(dir_okay=False))
    def plugins_keygen(private_key):
        """Create an Ed25519 signing key.  Keep the private file secret; share the public key."""
        from .trust import key_id, keygen, load_public

        if Path(private_key).exists():
            raise click.ClickException(f"{private_key} exists; not overwriting")
        pem, pub = keygen()
        fd = os.open(private_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        Path(private_key + ".pub").write_text(pub)
        click.echo(
            f"Private key: {private_key} (keep it secret)\nPublic key:  {private_key}.pub"
            f"\nKey id:      {key_id(load_public(pub))}\n\n{pub}"
        )

    @plugins_cli.command("sign")
    @click.argument("directory", type=click.Path(file_okay=False, exists=True))
    @click.option(
        "--key", "key_path", type=click.Path(dir_okay=False, exists=True), required=True
    )
    @click.option(
        "--signer", required=True, help="Your name, shown to people installing it."
    )
    def plugins_sign(directory, key_path, signer):
        """Write SIGNATURE.json covering every file in the plugin folder."""
        from .trust import sign

        doc = sign(Path(directory), Path(key_path).read_bytes(), signer)
        click.echo(
            f"Signed {doc['id']} {doc['version']}: {len(doc['files'])} files, key {doc['key_id']}"
        )

    @plugins_cli.command("prune")
    @click.argument("directory", type=click.Path(file_okay=False, exists=True))
    def plugins_prune(directory):
        """Delete from DIRECTORY (a copy made for a release) what its .releaseignore lists."""
        from .publish import prune_release

        for rel in prune_release(Path(directory)):
            click.echo(f"  left out {rel}")

    @plugins_cli.command("pack")
    @click.argument("directory", type=click.Path(file_okay=False, exists=True))
    @click.option("-o", "--output", type=click.Path(dir_okay=False), required=True)
    def plugins_pack(directory, output):
        """Zip a plugin folder for upload or a repository (prints the sha256)."""
        import hashlib

        from .publish import pack

        blob = pack(Path(directory))
        Path(output).write_bytes(blob)
        click.echo(f"{output}  sha256 {hashlib.sha256(blob).hexdigest()}")

    @plugins_cli.command("repo")
    @click.argument("source", type=click.Path(file_okay=False, exists=True))
    @click.argument("output", type=click.Path(file_okay=False))
    @click.option(
        "--key", "key_path", type=click.Path(dir_okay=False, exists=True), required=True
    )
    @click.option(
        "--name", required=True, help="The repository's name, shown when people add it."
    )
    @click.option("--description", default="")
    @click.option("--only", multiple=True, help="Only these plugin ids (repeatable).")
    def plugins_repo(source, output, key_path, name, description, only):
        """Build a signed repository from the plugin folders in SOURCE into OUTPUT.

        Each plugin is copied, pruned (.releaseignore), signed and zipped;
        SOURCE is not changed.  Publish OUTPUT on any web server.
        """
        from .installer import InstallError
        from .publish import build_repository

        try:
            doc = build_repository(
                Path(source),
                Path(output),
                Path(key_path).read_bytes(),
                name,
                description,
                list(only),
            )
        except (InstallError, ValueError) as exc:
            _fail(exc)
        for p in doc["plugins"]:
            click.echo(f"  {p['id']:<20} {p['version']:<8} {p.get('url', '')}")
        click.echo(
            f"Signed index for '{name}' with key {doc['key_id']}: {Path(output) / 'index.json'}"
        )

    @plugins_cli.command("build-index")
    @click.argument("sources", type=click.Path(dir_okay=False, exists=True))
    @click.argument("output", type=click.Path(file_okay=False))
    @click.option(
        "--key", "key_path", type=click.Path(dir_okay=False, exists=True), required=True
    )
    @click.option("--token", envvar="GITHUB_TOKEN", default="")
    def plugins_build_index(sources, output, key_path, token):
        """Build a signed index from SOURCES (plugin git repositories and their releases)."""
        import yaml

        from .installer import InstallError
        from .publish import build_index_from_sources

        try:
            doc = build_index_from_sources(
                yaml.safe_load(Path(sources).read_text()) or {},
                Path(output),
                Path(key_path).read_bytes(),
                token=token,
            )
        except (InstallError, ValueError) as exc:
            _fail(exc)
        for p in doc["plugins"]:
            click.echo(
                f"  {p['id']:<20} {p['version']:<8} {len(p.get('versions') or [])} version(s)"
            )
        for msg in doc["problems"]:
            click.echo(f"  ! {msg}", err=True)
        if doc["problems"] and not doc["plugins"]:
            raise SystemExit(1)

    @plugins_cli.command("yank")
    @click.argument("output", type=click.Path(file_okay=False, exists=True))
    @click.argument("plugin_id")
    @click.argument("version")
    @click.option(
        "--key", "key_path", type=click.Path(dir_okay=False, exists=True), required=True
    )
    @click.option(
        "--reason",
        default="",
        help="Shown to people who have it. Leave out to offer it again.",
    )
    def plugins_yank(output, plugin_id, version, key_path, reason):
        """Withdraw one version in a repository and re-sign its index."""
        from .installer import InstallError
        from .publish import yank

        try:
            yank(Path(output), Path(key_path).read_bytes(), plugin_id, version, reason)
        except (InstallError, ValueError, OSError) as exc:
            _fail(exc)
        click.echo(
            f"{plugin_id} {version}: {'withdrawn: ' + reason if reason else 'offered again'}"
        )
