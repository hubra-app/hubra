"""The audit log for one record, as the group/transaction/tier pages show it."""

from hubra.api.utils import log_audit

from tests.audit.test_audit_log import _get_audit, _make_member


def test_target_filter_keeps_only_that_record(client, db, auth_headers, seeded_db):
    alice = _make_member(db, seeded_db)
    log_audit(alice.id, "update_group", "Group", 7, "group 7")
    log_audit(alice.id, "update_group", "Group", 8, "group 8")
    log_audit(alice.id, "update_post", "Post", 7, "post 7")
    db.session.commit()

    resp = _get_audit(client, auth_headers, targetType="Group", targetId=7)
    assert resp.status_code == 200
    labels = {e["target_label"] for e in resp.get_json()["data"]}
    assert labels == {"group 7"}


def test_target_type_ignores_case(client, db, auth_headers, seeded_db):
    alice = _make_member(db, seeded_db)
    log_audit(alice.id, "create", "tier", 3, "tier 3")
    db.session.commit()

    resp = _get_audit(client, auth_headers, targetType="Tier", targetId=3)
    assert [e["target_label"] for e in resp.get_json()["data"]] == ["tier 3"]


def test_target_filter_needs_both_and_a_number(client, auth_headers):
    assert _get_audit(client, auth_headers, targetType="Group").status_code == 400
    assert _get_audit(client, auth_headers, targetId=3).status_code == 400
    assert (
        _get_audit(client, auth_headers, targetType="Group", targetId="x").status_code
        == 400
    )
