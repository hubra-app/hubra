"""``flask crypto``: check and rotate the key for secrets at rest;
``flask backups``: backup key pairs.

Changing ``FERNET_KEY``::

    FERNET_KEY=<new>  FERNET_OLD_KEYS=<old>   # restart with both
    flask crypto rotate                       # re-encrypt with <new>
    flask crypto check                        # exit 0: nothing left on <old>
    # then remove <old> from FERNET_OLD_KEYS and restart
"""

from __future__ import annotations

import click


def _print(report, rotated: bool) -> None:
    click.echo(f"  {report.total} encrypted values")
    click.echo(f"  {report.current} on the current key")
    if rotated:
        click.echo(f"  {report.rotated} re-encrypted with the current key")
    elif report.old_key:
        click.echo(f"  {report.old_key} still on an old key")
    for table, n in sorted(report.unreadable.items()):
        click.echo(f"  {n} in {table} that no key opens", err=True)


def register(app) -> None:
    @app.cli.group("crypto")
    def crypto_cli():
        """Check and rotate the encryption key for stored secrets."""

    @crypto_cli.command("check")
    def crypto_check():
        """Exit 0 when the current FERNET_KEY opens every stored value."""
        from hubra.core.services import secret_store

        report = secret_store.check()
        _print(report, rotated=False)
        if report.clean:
            click.echo("OK: old keys can be removed.")
            return
        if report.old_key:
            click.echo("Run `flask crypto rotate` before removing old keys.")
        if report.unreadable:
            click.echo(
                "Values no key opens were written with a key that is no "
                "longer configured; put it back in FERNET_OLD_KEYS.",
                err=True,
            )
        raise SystemExit(1)

    @crypto_cli.command("rotate")
    def crypto_rotate():
        """Re-encrypt every stored value with the current FERNET_KEY."""
        from hubra.core.services import secret_store

        report = secret_store.rotate()
        _print(report, rotated=True)
        if report.unreadable:
            raise SystemExit(1)
        click.echo("Done. Run `flask crypto check`, then remove the old key.")

    @app.cli.group("backups")
    def backups_cli():
        """Backup keys."""

    @backups_cli.command("keygen")
    def backups_keygen():
        """Print a new age key pair for BACKUP_PUBLIC_KEY or a club."""
        import subprocess

        result = subprocess.run(["age-keygen"], capture_output=True, check=True)
        click.echo(result.stdout.decode().strip())
        click.echo(
            "\nThe line `AGE-SECRET-KEY-1...` is the private key: keep it in a "
            "password manager, never on the server. The public key "
            "(age1...) goes in BACKUP_PUBLIC_KEY or `flask backups club-key`."
        )

    @backups_cli.command("club-key")
    @click.argument("slug")
    @click.argument("public_key", required=False)
    @click.option("--clear", is_flag=True, help="Remove the club's key")
    def backups_club_key(slug: str, public_key: str | None, clear: bool):
        """Show, set or remove a club's own backup public key.

        New backups of the club are encrypted to it as well as to
        BACKUP_PUBLIC_KEY, so the club can open them with its private key.
        """
        from sqlalchemy import select

        from hubra.core.extensions import db
        from hubra.core.models.tenant import Tenant
        from hubra.core.services.backup_crypto import split_keys, valid_public_key

        tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise click.ClickException(f"Club '{slug}' not found")
        if clear:
            tenant.backup_public_key = None
        elif public_key:
            keys = split_keys(public_key)
            if not keys or not all(valid_public_key(k) for k in keys):
                raise click.ClickException("Not an age public key (age1...)")
            tenant.backup_public_key = " ".join(keys)
        else:
            click.echo(tenant.backup_public_key or "(none)")
            return
        db.session.commit()
        click.echo(f"{slug}: {tenant.backup_public_key or 'no club key'}")
