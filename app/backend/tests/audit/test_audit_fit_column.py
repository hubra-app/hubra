"""Audit entries never fail the change they record because a name is long."""

from hubra.core.models.audit import AuditEntry


def test_long_actor_name_and_label_are_shortened(db, seeded_db):
    entry = AuditEntry(
        action="update_member",
        actor_name="A" * 255 + " " + "B" * 255,
        target_label="x" * 300,
    )
    assert len(entry.actor_name) == 255 and entry.actor_name.endswith("…")
    assert len(entry.target_label) == 255
    short = AuditEntry(action="x", actor_name="Ann Muster", target_label=None)
    assert short.actor_name == "Ann Muster" and short.target_label is None
