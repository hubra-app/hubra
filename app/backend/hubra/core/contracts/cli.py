"""``flask contracts``: what is offered, the outbox, and retrying dead rows."""

from __future__ import annotations

import json

import click
from flask import Flask


def register(app: Flask) -> None:
    @app.cli.group("contracts")
    def contracts_cli():
        """Events, actions and queries modules offer each other (docs/contracts.md)."""

    @contracts_cli.command("list")
    @click.option(
        "--json",
        "as_json",
        is_flag=True,
        help="With JSON schemas, for the plugin index.",
    )
    def contracts_list(as_json: bool):
        """Every contract on offer, with who offers it."""
        from . import registry

        offers = sorted(registry.offers().values(), key=lambda o: o.contract.name)
        if as_json:
            click.echo(json.dumps([o.to_dict() for o in offers], indent=2))
            return
        for o in offers:
            c = o.contract
            perm = f"  needs {c.perm}" if c.perm else ""
            click.echo(f"{c.kind:6} {c.name} v{c.version}  ({o.module_code}){perm}")

    @contracts_cli.command("outbox")
    @click.option("--dead", is_flag=True, help="List the rows that gave up.")
    def contracts_outbox(dead: bool):
        """Rows per status, or the dead ones."""
        from sqlalchemy import func, select

        from hubra.core.extensions import db
        from hubra.core.models.contract_outbox import ContractMessage

        if dead:
            rows = db.session.scalars(
                select(ContractMessage)
                .where(ContractMessage.status == "dead")
                .order_by(ContractMessage.id.desc())
                .limit(50)
            ).all()
            for r in rows:
                click.echo(
                    f"{r.uid} {r.kind} {r.name} -> {r.module_code} club {r.tenant_id}"
                    f" after {r.attempts}: {r.last_error}"
                )
            return
        counts = db.session.execute(
            select(ContractMessage.status, func.count()).group_by(
                ContractMessage.status
            )
        ).all()
        for status, n in sorted(counts):
            click.echo(f"{status:8} {n}")

    @contracts_cli.command("retry")
    @click.argument("uid")
    def contracts_retry(uid: str):
        """Give a dead row another round of attempts."""
        from . import outbox

        if not outbox.replay(uid):
            raise click.ClickException(f"No dead row {uid}")
        click.echo(f"{uid} queued again")
