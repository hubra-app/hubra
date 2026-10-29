"""Adding and removing a club's domain is in the club's audit log."""

from sqlalchemy import select

from tests.test_domain_api import auth_headers, tenant_ctx  # noqa: F401


def test_domain_changes_are_audited(tenant_ctx, client, auth_headers, db):  # noqa: F811
    from hubra.core.models.audit import AuditEntry

    resp = client.post(
        "/api/v1/admin/domains", json={"domain": "verein.ch"}, headers=auth_headers
    )
    domain_id = resp.get_json()["domain"]["id"]
    client.delete(f"/api/v1/admin/domains/{domain_id}", headers=auth_headers)

    rows = db.session.execute(
        select(AuditEntry.action, AuditEntry.target_label, AuditEntry.actor_id).where(
            AuditEntry.target_type == "Domain"
        )
    ).all()
    assert sorted(r[:2] for r in rows) == [
        ("add_domain", "verein.ch"),
        ("remove_domain", "verein.ch"),
    ]
    assert all(r[2] is not None for r in rows)
