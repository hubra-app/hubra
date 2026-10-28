"""flask list-tenants prints one line per club."""

from hubra.core.models.tenant import Tenant


def test_list_tenants_cli(app, db):
    db.session.add(
        Tenant(name="Demo Club", slug="demo", plan="starter", status="active")
    )
    db.session.commit()

    result = app.test_cli_runner().invoke(args=["list-tenants"])

    assert result.exit_code == 0, result.output
    assert "demo" in result.output
    assert "Demo Club" in result.output
