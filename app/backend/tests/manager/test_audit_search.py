"""Audit search across the platform log and the clubs' logs, with export."""

from __future__ import annotations

from datetime import datetime, timezone

from hubra.core.models.audit import AuditEntry
from hubra.core.models.tenant import GlobalAuditEntry

BASE = "/api/v1/system/audit"


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def _seed(db, tenant_pair, seeded_db):
    a = tenant_pair["tenant_a"]
    staff = seeded_db["user"]
    db.session.add_all(
        [
            GlobalAuditEntry(
                tenant_id=a.id,
                actor_id=staff.id,
                action="tenant.limits",
                target_type="Tenant",
                target_id=str(a.id),
                details={"after": {"members": 50}},
                ip_address="10.0.0.7",
                time=_at(20),
            ),
            GlobalAuditEntry(
                tenant_id=None,
                actor_id=staff.id,
                action="platform.settings.update",
                target_type="platform_setting",
                target_id="mail.relay",
                details={"key": "mail.relay"},
                time=_at(22),
            ),
            # Club log (on SQLite: the one audit_entries table).
            AuditEntry(
                action="member.update",
                actor_name="Anna Kassierin",
                target_type="Member",
                target_id=12,
                target_label="=HYPERLINK(evil)",
                time=_at(21),
            ),
            AuditEntry(
                action="invoice.create",
                actor_name="Anna Kassierin",
                target_type="Invoice",
                target_id=3,
                target_label="Rechnung 2026-114",
                time=_at(25),
            ),
        ]
    )
    db.session.commit()
    return a


def test_platform_entries_with_people_and_clubs(
    client, db, staff_headers, tenant_pair, seeded_db
):
    a = _seed(db, tenant_pair, seeded_db)
    body = client.get(BASE + "/search").get_json()
    # Without a club chosen, SQLite only has the platform log to offer.
    assert [e["action"] for e in body["entries"]] == [
        "platform.settings.update",
        "tenant.limits",
    ]
    limits = body["entries"][1]
    assert limits["club"] == "Tenant A" and limits["tenant_id"] == a.id
    assert limits["source"] == "platform"
    assert limits["actor_email"] == seeded_db["user"].email
    assert limits["details"] == {"after": {"members": 50}}


def test_one_club_merges_both_logs(sqlite_only, client, db, staff_headers, tenant_pair, seeded_db):
    a = _seed(db, tenant_pair, seeded_db)
    # Up to October: the staff sign-in (today) is in the club log too.
    body = client.get(f"{BASE}/search?tenant_id={a.id}&to=2026-10-31").get_json()
    assert [(e["source"], e["action"]) for e in body["entries"]] == [
        ("club", "invoice.create"),
        ("club", "member.update"),
        ("platform", "tenant.limits"),
    ]
    assert body["total"] == 3
    assert body["entries"][0]["actor"] == "Anna Kassierin"
    assert body["entries"][0]["club"] == "Tenant A"

    only_club = client.get(
        f"{BASE}/search?tenant_id={a.id}&source=club&to=2026-10-31"
    ).get_json()
    assert {e["source"] for e in only_club["entries"]} == {"club"}


def test_filters(sqlite_only, client, db, staff_headers, tenant_pair, seeded_db):
    a = _seed(db, tenant_pair, seeded_db)

    def actions(qs):
        url = f"{BASE}/search?tenant_id={a.id}&{qs}&to=2026-10-31"  # first wins
        body = client.get(url).get_json()
        return [e["action"] for e in body["entries"]]

    assert actions("q=rechnung") == ["invoice.create"]
    assert actions("q=10.0.0") == ["tenant.limits"]  # IP
    assert actions("q=members") == ["tenant.limits"]  # details
    assert actions("action=member") == ["member.update"]  # a prefix
    assert actions("from=2026-10-21&to=2026-10-21") == ["member.update"]
    assert actions("from=2026-10-21") == ["invoice.create", "member.update"]
    assert actions("q=100%25") == []  # % is literal
    body = client.get(f"{BASE}/search?tenant_id={a.id}&hide_logins=1").get_json()
    assert "login" not in [e["action"] for e in body["entries"]]
    assert body["total"] == 3
    paged = client.get(
        f"{BASE}/search?tenant_id={a.id}&to=2026-10-31&per_page=1&page=2"
    ).get_json()
    assert [e["action"] for e in paged["entries"]] == ["member.update"]
    assert paged["total"] == 3


def test_bad_filters(client, staff_headers):
    for qs in (
        "source=x",
        "tenant_id=a",
        "from=gestern",
        "from=2026-10-02&to=2026-10-01",
    ):
        assert client.get(f"{BASE}/search?{qs}").status_code == 400, qs


def test_export_is_csv_and_is_logged(sqlite_only, client, db, staff_headers, tenant_pair, seeded_db):
    a = _seed(db, tenant_pair, seeded_db)
    resp = client.get(f"{BASE}/export?tenant_id={a.id}&to=2026-10-31")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert resp.headers["X-Rows"] == "3"
    assert "hubra-audit-" in resp.headers["Content-Disposition"]
    text = resp.get_data(as_text=True)
    assert text.startswith("﻿time;source;club_id;club;action")
    lines = text.strip().splitlines()
    assert len(lines) == 4
    # A cell a spreadsheet would run as a formula is defused.
    assert "'=HYPERLINK(evil)" in text

    db.session.expire_all()
    logged = db.session.query(GlobalAuditEntry).filter_by(action="audit.export").one()
    assert logged.details["rows"] == 3
    assert logged.details["filters"] == {"tenant_id": a.id, "to": "2026-10-31"}


def test_club_admin_cannot_search(client, auth_headers):
    assert client.get(BASE + "/search", headers=auth_headers).status_code == 403
    assert client.get(BASE + "/export", headers=auth_headers).status_code == 403
