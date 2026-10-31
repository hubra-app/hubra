"""The audit log for one member, as the member page shows it."""

from hubra.api.utils import log_audit

from tests.audit.test_audit_log import _get_audit, _make_member


def test_member_filter_keeps_what_they_did_and_what_was_done_to_them(
    client, db, auth_headers, seeded_db
):
    alice = _make_member(db, seeded_db)
    bob = _make_member(db, seeded_db, "Bob", "Test", "bob@test.ch")
    log_audit(alice.id, "create_post", "Post", 1, "by alice")
    log_audit(bob.id, "update_member", "Member", alice.id, "about alice")
    log_audit(bob.id, "update_member", "Member", bob.id, "about bob")
    log_audit(bob.id, "update_post", "Post", alice.id, "post with alice's id")
    db.session.commit()

    resp = _get_audit(client, auth_headers, memberId=alice.id)
    assert resp.status_code == 200
    labels = {e["target_label"] for e in resp.get_json()["data"]}
    assert labels == {"by alice", "about alice"}


def test_member_filter_rejects_a_non_number(client, auth_headers):
    resp = _get_audit(client, auth_headers, memberId="x")
    assert resp.status_code == 400
