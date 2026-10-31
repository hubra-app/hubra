"""``flask crypto``: check and rotate the key for secrets at rest.

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
