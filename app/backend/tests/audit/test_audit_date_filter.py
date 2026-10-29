"""The club audit log's date filter."""

from hubra.api.utils import log_audit

from tests.audit.test_audit_log import _get_audit, _make_member


def test_to_date_includes_that_whole_day(client, db, auth_headers, seeded_db):
    """?to=YYYY-MM-DD keeps the entries from later on that day."""
    from datetime import date

    member = _make_member(db, seeded_db)
    log_audit(member.id, "create_member", "Member", member.id, "x")
    db.session.commit()

    today = date.today().isoformat()
    resp = _get_audit(client, auth_headers, **{"from": today, "to": today})
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]) >= 1
