"""Integration tests for retention_cleanup and reconcile_mail Celery tasks.

Imports inside mail_tasks.py are deferred (inside function bodies), so patches
must target the source modules (e.g. hubra.core.services.wildduck.try_get_client),
not hubra.core.tasks.mail_tasks.*
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


from hubra.core.models.member import Member
from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_member(
    db, seeded_db, *, email: str, is_disabled=False, **overrides
) -> Member:
    role = seeded_db["role"]
    user = User(
        email=email, first_name="Test", last_name="Member", is_disabled=is_disabled
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    m = Member(
        user_id=user.id,
        status="active",
        **overrides,
    )
    m.roles = [role]
    db.session.add(m)
    db.session.commit()
    return m


def _make_member_mma(
    db, member, *, wildduck_user_id=None, forwarding_enabled=False, retention_days=None
):
    """Create a ManagedMailAddress for a member (hub-pattern style)."""
    addr = ManagedMailAddress(
        address=f"{member.email.split('@')[0]}@club.ch",
        address_type="mailbox",
        is_protected=False,
        wildduck_user_id=wildduck_user_id,
        wildduck_id=wildduck_user_id,
        forwarding_enabled=forwarding_enabled,
        forward_enabled=forwarding_enabled,
        kind="member",
        enabled=True,
        is_enabled=True,
        local_part=member.email.split("@")[0],
        domain="club.ch",
        owner_type="member",
        owner_id=member.id,
        retention=retention_days * 86400000 if retention_days else None,
    )
    db.session.add(addr)
    db.session.commit()
    return addr


def _make_group(db, *, name: str, **overrides) -> Group:
    g = Group(name=name, **overrides)
    db.session.add(g)
    db.session.commit()
    return g


def _ms(dt: datetime) -> int:
    """Convert datetime to Unix milliseconds."""
    return int(dt.timestamp() * 1000)


def _mock_wd_with_folders(folders: list[dict], messages_by_folder: dict) -> MagicMock:
    """Build a WildDuck mock that returns folders and per-folder messages.

    folders: list of {"id": "...", "path": "..."} dicts
    messages_by_folder: {folder_id: [{"id": "msg_id", "date": ms_timestamp}, ...]}
    """
    mock_wd = MagicMock()
    mock_wd.list_mailboxes.return_value = {"results": folders}

    def _list_messages(user_id, mailbox, limit=250, page=1):
        msgs = messages_by_folder.get(mailbox, [])
        return {"results": msgs, "total": len(msgs)}

    mock_wd.list_user_messages.side_effect = _list_messages
    return mock_wd


# ── retention_cleanup tests ───────────────────────────────────────────────────


def test_retention_cleanup_deletes_old_messages(app, db, seeded_db):
    """Member with retention_days=30; message 40 days old in INBOX → deleted."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    member = _make_member(
        db,
        seeded_db,
        email="old@example.com",
        retention_days=30,
    )
    _make_member_mma(db, member, wildduck_user_id="wd1")

    mock_wd = _mock_wd_with_folders(
        folders=[{"id": "inbox-id", "path": "INBOX"}],
        messages_by_folder={
            "inbox-id": [{"id": "msg1", "date": _ms(now - timedelta(days=40))}]
        },
    )

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    mock_wd.delete_user_message.assert_called_once_with("wd1", "inbox-id", "msg1")
    assert result["deleted"] == 1
    assert result["processed"] == 1


def test_retention_cleanup_deletes_across_all_folders(app, db, seeded_db):
    """Old messages in both INBOX and Sent are deleted."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    member = _make_member(
        db,
        seeded_db,
        email="allfolders@example.com",
        retention_days=30,
    )
    _make_member_mma(db, member, wildduck_user_id="wd1")

    mock_wd = _mock_wd_with_folders(
        folders=[
            {"id": "inbox-id", "path": "INBOX"},
            {"id": "sent-id", "path": "Sent"},
        ],
        messages_by_folder={
            "inbox-id": [{"id": "msg1", "date": _ms(now - timedelta(days=40))}],
            "sent-id": [{"id": "msg2", "date": _ms(now - timedelta(days=35))}],
        },
    )

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    assert result["deleted"] == 2
    assert result["processed"] == 1
    mock_wd.delete_user_message.assert_any_call("wd1", "inbox-id", "msg1")
    mock_wd.delete_user_message.assert_any_call("wd1", "sent-id", "msg2")


def test_retention_cleanup_skips_fresh_messages(app, db, seeded_db):
    """Member with retention_days=30; message 10 days old → not deleted."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    member = _make_member(
        db,
        seeded_db,
        email="fresh@example.com",
        retention_days=30,
    )
    _make_member_mma(db, member, wildduck_user_id="wd1")

    mock_wd = _mock_wd_with_folders(
        folders=[{"id": "inbox-id", "path": "INBOX"}],
        messages_by_folder={
            "inbox-id": [{"id": "msg1", "date": _ms(now - timedelta(days=10))}]
        },
    )

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    mock_wd.delete_user_message.assert_not_called()
    assert result["deleted"] == 0


def test_retention_cleanup_skips_no_wildduck_id(app, db, seeded_db):
    """Member MMA with no wildduck_user_id → filtered at DB query level."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    member = _make_member(
        db,
        seeded_db,
        email="noid@example.com",
        retention_days=30,
    )
    _make_member_mma(db, member, wildduck_user_id=None)

    mock_wd = MagicMock()
    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    mock_wd.list_mailboxes.assert_not_called()
    assert result["processed"] == 0


def test_retention_cleanup_skips_member_with_no_retention(app, db, seeded_db):
    """Member with retention_days=None on MMA and kind=member → skipped (retention OFF by default)."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    member = _make_member(
        db,
        seeded_db,
        email="noretention@example.com",
        retention_days=None,
    )
    _make_member_mma(db, member, wildduck_user_id="wd1", retention_days=None)

    mock_wd = _mock_wd_with_folders(
        folders=[{"id": "inbox-id", "path": "INBOX"}],
        messages_by_folder={
            "inbox-id": [{"id": "msg1", "date": _ms(now - timedelta(days=400))}]
        },
    )
    mock_setting_svc = MagicMock()
    mock_setting_svc.get.return_value = None

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch(
            "hubra.api.settings.services.SettingService.get",
            mock_setting_svc.get,
        ):
            result = retention_cleanup.run()

    mock_wd.delete_user_message.assert_not_called()
    assert result["deleted"] == 0
    assert result["processed"] == 0


def test_retention_cleanup_uses_mma_retention_days(app, db, seeded_db):
    """Member with retention_days=60 on MMA → messages older than 60 days deleted."""
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    member = _make_member(
        db,
        seeded_db,
        email="mma-retention@example.com",
        retention_days=None,
    )
    _make_member_mma(db, member, wildduck_user_id="wd1", retention_days=60)

    mock_wd = _mock_wd_with_folders(
        folders=[{"id": "inbox-id", "path": "INBOX"}],
        messages_by_folder={
            "inbox-id": [{"id": "msg1", "date": _ms(now - timedelta(days=70))}]
        },
    )

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    mock_wd.delete_user_message.assert_called_once_with("wd1", "inbox-id", "msg1")
    assert result["deleted"] == 1
    assert result["processed"] == 1


def test_retention_cleanup_wildduck_error_continues(app, db, seeded_db):
    """Two members; first raises WildDuckError; second succeeds → task completes."""
    from hubra.core.services.wildduck import WildDuckError
    from hubra.core.tasks.mail_tasks import retention_cleanup

    now = datetime.now(timezone.utc)
    m1 = _make_member(
        db,
        seeded_db,
        email="error@example.com",
        retention_days=30,
    )
    _make_member_mma(db, m1, wildduck_user_id="wd-error")
    m2 = _make_member(
        db,
        seeded_db,
        email="ok@example.com",
        retention_days=30,
    )
    _make_member_mma(db, m2, wildduck_user_id="wd-ok")

    mock_wd = MagicMock()

    def list_mailboxes_side(user_id):
        if user_id == "wd-error":
            raise WildDuckError(503, "connection refused")
        return {"results": [{"id": "inbox-id", "path": "INBOX"}]}

    def list_messages_side(user_id, mailbox, **kwargs):
        return {
            "results": [{"id": "msg2", "date": _ms(now - timedelta(days=40))}],
            "total": 1,
        }

    mock_wd.list_mailboxes.side_effect = list_mailboxes_side
    mock_wd.list_user_messages.side_effect = list_messages_side

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        result = retention_cleanup.run()

    assert result["errors"] == 1
    assert result["processed"] == 1
    assert result["deleted"] == 1


# ── cleanup_token_blocklist tests ─────────────────────────────────────────────


def test_cleanup_token_blocklist_deletes_old_tokens(app, db):
    """Tokens older than 30 days are removed; recent ones are kept."""
    from hubra.core.models.token import TokenBlocklist
    from hubra.core.tasks.mail_tasks import cleanup_token_blocklist

    old_token = TokenBlocklist(
        jti="old-jti",
        type="access",
        created_at=datetime.now(timezone.utc) - timedelta(days=31),
    )
    recent_token = TokenBlocklist(
        jti="recent-jti",
        type="access",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.session.add_all([old_token, recent_token])
    db.session.commit()

    old_id = old_token.id
    recent_id = recent_token.id
    # Expunge before task runs so bulk DELETE doesn't hit the timezone-naive
    # vs offset-aware comparison in SQLAlchemy's synchronize_session evaluator.
    db.session.expunge_all()

    result = cleanup_token_blocklist.run()

    assert result["deleted"] == 1
    remaining = db.session.get(TokenBlocklist, recent_id)
    assert remaining is not None
    gone = db.session.get(TokenBlocklist, old_id)
    assert gone is None


def test_cleanup_token_blocklist_no_old_tokens(app, db):
    """No tokens older than 30 days → deleted=0."""
    from hubra.core.tasks.mail_tasks import cleanup_token_blocklist

    result = cleanup_token_blocklist.run()
    assert result["deleted"] == 0


def test_reconcile_mail_provisions_unprovisioned_group_mma(app, db, seeded_db):
    """Group MMA with kind=group, address_type=mailbox → reconcile_mail provisions it."""
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.tasks.mail_tasks import reconcile_mail

    group = _make_group(db, name="Unprov MMA Group")
    addr = ManagedMailAddress(
        address="unprov-mma@club.ch",
        address_type="mailbox",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
        kind="group",
        enabled=True,
        local_part="unprov-mma",
        domain="club.ch",
    )
    db.session.add(addr)
    db.session.commit()

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-group-001"}
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_wd.add_address_to_user.return_value = {"id": "addr-001"}

    with patch("hubra.core.services.wildduck.try_get_client", return_value=mock_wd):
        with patch(
            "hubra.core.services.mail_provisioning.try_get_client",
            return_value=mock_wd,
        ):
            with patch(
                "hubra.core.services.mail_provisioning._resolve_group_member_targets",
                return_value=["member@example.ch"],
            ):
                result = reconcile_mail.run()

    assert result["provisioned"] == 1
    assert result["errors"] == 0
    mock_wd.create_user.assert_called_once()
    db.session.refresh(addr)
    assert addr.wildduck_id == "wd-group-001"


# Member reconciliation (stale-ID, drift detection, transient errors) is now
# handled by the 15-minute reconcile_mail task via ensure_mailbox primitives.


# ── Beat schedule tests ───────────────────────────────────────────────────────


def test_beat_schedule_contains_retention_cleanup():
    """celery_app beat_schedule includes retention-cleanup-daily."""
    from hubra.core.tasks import celery_app

    assert "retention-cleanup-daily" in celery_app.conf.beat_schedule


def test_beat_schedule_no_legacy_mail_reconcile():
    """The no-op 5-minute mail_reconcile was removed; reconcile_mail covers it."""
    from hubra.core.tasks import celery_app

    assert "mail-reconcile-5min" not in celery_app.conf.beat_schedule


def test_beat_schedule_contains_token_blocklist_cleanup():
    """celery_app beat_schedule includes cleanup-token-blocklist-daily."""
    from hubra.core.tasks import celery_app

    assert "cleanup-token-blocklist-daily" in celery_app.conf.beat_schedule


def test_beat_schedule_contains_reconcile_mail():
    """celery_app beat_schedule includes mail-reconcile-v2-15min."""
    from hubra.core.tasks import celery_app

    assert "mail-reconcile-v2-15min" in celery_app.conf.beat_schedule


def test_beat_schedule_contains_check_mailbox_quota():
    """celery_app beat_schedule includes check-mailbox-quota-hourly."""
    from hubra.core.tasks import celery_app

    assert "check-mailbox-quota-hourly" in celery_app.conf.beat_schedule


def test_beat_schedule_no_ensure_mmas_15min():
    """ensure-mmas-15min removed (redundant — reconcile_mail covers auto-creation)."""
    from hubra.core.tasks import celery_app

    assert "ensure-mmas-15min" not in celery_app.conf.beat_schedule


def test_beat_schedule_no_ensure_mmas_hourly():
    """Old hourly entry must be removed."""
    from hubra.core.tasks import celery_app

    assert "ensure-mmas-hourly" not in celery_app.conf.beat_schedule


# ── resolve_local_part tests ────────────────────────────────────────────────


def test_resolve_local_part_normalizes(app, db):
    """resolve_local_part lowercases, replaces umlauts, collapses special chars."""
    from hubra.core.services.mail_provisioning import resolve_local_part

    assert resolve_local_part("Müller") == "mueller"
    assert resolve_local_part("MÖLLER") == "moeller"
    assert resolve_local_part("straße") == "strasse"
    assert resolve_local_part("  Foo!Bar  ") == "foo.bar"
    assert resolve_local_part(".foo..bar.") == "foo.bar"
    assert resolve_local_part("-foo-bar-") == "foo-bar"


def test_resolve_local_part_truncates(app, db):
    """Local part longer than 64 chars is truncated."""
    from hubra.core.services.mail_provisioning import resolve_local_part

    long_name = "a" * 100
    result = resolve_local_part(long_name)
    assert len(result) == 64
    assert result == "a" * 64


def test_resolve_local_part_empty_falls_back(app, db):
    """Empty or all-symbol local part falls back to 'mail'."""
    from hubra.core.services.mail_provisioning import resolve_local_part

    assert resolve_local_part("") == "mail"
    assert resolve_local_part("...") == "mail"
    assert resolve_local_part("-.-") == "mail"


def test_resolve_local_part_collision_suffixes(app, db):
    """When the local part is taken, appends smallest free integer."""
    from hubra.core.models.setting import Setting
    from hubra.core.services.mail_provisioning import resolve_local_part

    Setting.__table__.create(db.session.get_bind(), checkfirst=True)
    db.session.add(Setting(key="mail.domain", value="hubra.club"))
    db.session.commit()

    from hubra.core.models.managed_mail import ManagedMailAddress

    mma = ManagedMailAddress(
        address="vorstand@hubra.club",
        address_type="mailbox",
        kind="group",
        local_part="vorstand",
        domain="hubra.club",
    )
    db.session.add(mma)
    db.session.commit()

    assert resolve_local_part("vorstand") == "vorstand2"

    # Now take "vorstand2" too — should skip to "vorstand3"
    mma2 = ManagedMailAddress(
        address="vorstand2@hubra.club",
        address_type="alias",
        kind="group",
        local_part="vorstand2",
        domain="hubra.club",
    )
    db.session.add(mma2)
    db.session.commit()

    assert resolve_local_part("vorstand") == "vorstand3"


def test_resolve_local_part_free_when_not_taken(app, db):
    """Free local part returns as-is (after normalization)."""
    from hubra.core.services.mail_provisioning import resolve_local_part

    assert resolve_local_part("free-name") == "free-name"


# ── Provisioning primitive tests ──────────────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_mailbox_creates(mock_tgc, app, db):
    """ensure_mailbox creates a new WildDuck user when wildduck_id is None."""
    from hubra.core.services.mail_provisioning import ensure_mailbox
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-new"}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
        display_name="Test User",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_mailbox(mma)

    mock_wd.create_user.assert_called_once()
    assert mma.wildduck_id == "wd-new"
    assert mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_mailbox_updates(mock_tgc, app, db):
    """ensure_mailbox updates an existing WildDuck user when wildduck_id is set."""
    from hubra.core.services.mail_provisioning import ensure_mailbox
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = {"id": "wd-existing"}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
        wildduck_id="wd-existing",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_mailbox(mma)

    mock_wd.update_user_attributes.assert_called_once_with(
        "wd-existing", name="test", quota=mma.quota_bytes or 1073741824
    )


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_mailbox_recreates_when_not_found(mock_tgc, app, db):
    """Ensure_mailbox re-creates a user when wildduck_id returns 404."""
    from hubra.core.services.mail_provisioning import ensure_mailbox
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.safe_get_user.return_value = None  # user not found
    mock_wd.create_user.return_value = {"id": "wd-recreated"}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="group",
        local_part="test",
        domain="hubra.club",
        wildduck_id="wd-stale",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_mailbox(mma)

    assert mma.wildduck_id == "wd-recreated"
    mock_wd.create_user.assert_called_once()


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_mailbox_skips_when_not_configured(mock_tgc, app, db):
    """ensure_mailbox is a no-op when WildDuck is not configured."""
    from hubra.core.services.mail_provisioning import ensure_mailbox
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_tgc.return_value = None

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_mailbox(mma)
    assert mma.wildduck_id is None


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_alias_for_mailbox(mock_tgc, app, db):
    """ensure_alias adds address to user when address_type is mailbox."""
    from hubra.core.services.mail_provisioning import ensure_alias
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
        wildduck_id="wd-user",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_alias(mma)

    mock_wd.add_address_to_user.assert_called_once_with(
        "wd-user", "test@hubra.club", allow_wildcard=False
    )
    assert mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_alias_forwarding(mock_tgc, app, db):
    """ensure_alias creates a forwarding alias when address_type is alias."""
    from hubra.core.services.mail_provisioning import ensure_alias
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.safe_get_address.return_value = None
    mock_wd.create_forwarding_alias.return_value = {"id": "wd-alias-new"}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="forward@hubra.club",
        address_type="alias",
        kind=None,
        local_part="forward",
        domain="hubra.club",
        display_name="Forward Alias",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_alias(mma)

    mock_wd.create_forwarding_alias.assert_called_once_with(
        "forward@hubra.club", targets=[], name="Forward Alias"
    )
    assert mma.wildduck_id == "wd-alias-new"
    assert mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_forwarding_sets_targets(mock_tgc, app, db):
    """ensure_forwarding updates user targets to the given list."""
    from hubra.core.services.mail_provisioning import ensure_forwarding
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
        wildduck_id="wd-user",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_forwarding(mma, ["user@example.com"])

    mock_wd.update_user_attributes.assert_called_once_with(
        "wd-user", targets=["user@example.com"]
    )
    assert mma.sync_state == "ok"


@patch("hubra.core.services.mail_provisioning.try_get_client")
def test_ensure_absent_removes(mock_tgc, app, db):
    """ensure_absent removes WildDuck user/alias and clears wildduck_id."""
    from hubra.core.services.mail_provisioning import ensure_absent
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="test",
        domain="hubra.club",
        wildduck_id="wd-remove",
    )
    db.session.add(mma)
    db.session.commit()

    ensure_absent(mma)

    mock_wd.safe_delete_user.assert_called_once_with("wd-remove")
    assert mma.wildduck_id is None
    assert mma.sync_state == "ok"


# ── reconcile_mail tests ────────────────────────────────────────────────────


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_provisions_mailbox(mock_wd_tgc, mock_mp_tgc, app, db):
    """reconcile_mail calls ensure_mailbox for mailbox-backed MMA."""
    from hubra.core.tasks.mail_tasks import reconcile_mail
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-created"}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="test@hubra.club",
        address_type="mailbox",
        kind=None,
        local_part="test",
        domain="hubra.club",
    )
    db.session.add(mma)
    db.session.commit()

    result = reconcile_mail.run()

    assert result["provisioned"] == 1
    assert result["errors"] == 0
    mock_wd.create_user.assert_called_once()


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_removes_orphans(mock_wd_tgc, mock_mp_tgc, app, db):
    """reconcile_mail sweeps WildDuck users not backed by any MMA."""
    from hubra.core.tasks.mail_tasks import reconcile_mail
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.list_users.return_value = {
        "results": [{"id": "wd-orphan"}, {"id": "wd-managed"}]
    }
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="managed@hubra.club",
        address_type="mailbox",
        kind=None,
        local_part="managed",
        domain="hubra.club",
        wildduck_id="wd-managed",
    )
    db.session.add(mma)
    db.session.commit()

    result = reconcile_mail.run()

    mock_wd.safe_delete_user.assert_called_once_with("wd-orphan")
    assert result["orphans_removed"] == 1


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_keeps_mailboxes_of_other_clubs(mock_wd_tgc, mock_mp_tgc, app, db):
    """One club's orphan sweep must not delete another club's mailboxes."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    wd = MagicMock()
    wd.list_users.return_value = {
        "results": [{"id": "wd-other-club"}, {"id": "wd-orphan"}]
    }
    mock_wd_tgc.return_value = wd
    mock_mp_tgc.return_value = wd

    with patch(
        "hubra.core.services.mail_server.managed_index",
        return_value={"wd-other-club": {"club": {"slug": "club-b"}}},
    ) as index:
        result = reconcile_mail.run()

    wd.safe_delete_user.assert_called_once_with("wd-orphan")
    assert result["orphans_removed"] == 1
    # Suspended clubs and clubs with mail off still claim their mailboxes.
    index.assert_called_once_with(every_club=True)


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_continues_on_error(mock_wd_tgc, mock_mp_tgc, app, db):
    """reconcile_mail increments error count and continues on WildDuckError."""
    from hubra.core.services.wildduck import WildDuckError
    from hubra.core.tasks.mail_tasks import reconcile_mail
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.create_user.side_effect = WildDuckError(503, "down")
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="error@hubra.club",
        address_type="mailbox",
        kind=None,
        local_part="error",
        domain="hubra.club",
    )
    db.session.add(mma)
    db.session.commit()

    result = reconcile_mail.run()

    assert result["errors"] == 1


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_provisions_active_member(
    mock_wd_tgc, mock_mp_tgc, app, db, seeded_db
):
    """reconcile_mail provisions mailbox for active member with kind=member."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    mock_wd = MagicMock()
    mock_wd.create_user.return_value = {"id": "wd-member-001"}
    mock_wd.list_user_addresses.return_value = {"results": []}
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    member = _make_member(db, seeded_db, email="active-member@example.com")
    _make_member_mma(db, member, wildduck_user_id=None, forwarding_enabled=False)

    result = reconcile_mail.run()

    mock_wd.create_user.assert_called_once()
    assert result["provisioned"] >= 1
    assert result["errors"] == 0


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_disables_archived_member(
    mock_wd_tgc, mock_mp_tgc, app, db, seeded_db
):
    """reconcile_mail sets disabled=True on WildDuck user for archived member."""
    from datetime import datetime, timezone

    from hubra.core.tasks.mail_tasks import reconcile_mail

    mock_wd = MagicMock()
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    member = _make_member(db, seeded_db, email="archived@example.com")
    member.archived_at = datetime.now(timezone.utc)
    db.session.commit()
    _make_member_mma(db, member, wildduck_user_id="wd-archived")

    result = reconcile_mail.run()

    mock_wd.update_user_attributes.assert_any_call("wd-archived", disabled=True)
    assert result["errors"] == 0


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_disables_disabled_member(
    mock_wd_tgc, mock_mp_tgc, app, db, seeded_db
):
    """reconcile_mail sets disabled=True on WildDuck user for is_disabled member."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    mock_wd = MagicMock()
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    member = _make_member(db, seeded_db, email="disabled@example.com", is_disabled=True)
    _make_member_mma(db, member, wildduck_user_id="wd-disabled")

    result = reconcile_mail.run()

    mock_wd.update_user_attributes.assert_any_call("wd-disabled", disabled=True)
    assert result["errors"] == 0


@patch("hubra.core.services.mail_provisioning.try_get_client")
@patch("hubra.core.services.wildduck.try_get_client")
def test_reconcile_mail_skips_member_mma_enabled_false(
    mock_wd_tgc, mock_mp_tgc, app, db, seeded_db
):
    """reconcile_mail skips member MMA with enabled=False (continue, no provisioning)."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    mock_wd = MagicMock()
    mock_wd.list_users.return_value = {"results": []}
    mock_wd_tgc.return_value = mock_wd
    mock_mp_tgc.return_value = mock_wd

    member = _make_member(db, seeded_db, email="maildisabled@example.com")
    addr = _make_member_mma(db, member, wildduck_user_id=None)
    addr.enabled = False
    db.session.commit()

    reconcile_mail.run()

    mock_wd.create_user.assert_not_called()


@patch("hubra.core.services.email._send")
@patch("hubra.core.services.wildduck.try_get_client")
def test_check_mailbox_quota_sends_alert(mock_tgc, mock_send, app, db):
    """check_mailbox_quota sends alert when mailbox is at/above 90%."""
    from hubra.core.tasks.mail_tasks import check_mailbox_quota
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.get_user_quota.return_value = {"allowed": 1000000, "used": 950000}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="full@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="full",
        domain="hubra.club",
        wildduck_id="wd-full",
    )
    db.session.add(mma)
    db.session.commit()

    result = check_mailbox_quota.run()

    assert result["alerts_sent"] >= 1  # postmaster always gets one
    assert mma.last_quota_alert_at is not None


@patch("hubra.core.services.wildduck.try_get_client")
def test_check_mailbox_quota_skips_under_90(mock_tgc, app, db):
    """check_mailbox_quota does not alert when usage is under 90%."""
    from hubra.core.tasks.mail_tasks import check_mailbox_quota
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.get_user_quota.return_value = {"allowed": 1000000, "used": 500000}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="half@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="half",
        domain="hubra.club",
        wildduck_id="wd-half",
    )
    db.session.add(mma)
    db.session.commit()

    result = check_mailbox_quota.run()

    assert result["alerts_sent"] == 0


@patch("hubra.core.services.wildduck.try_get_client")
def test_check_mailbox_quota_respects_cooldown(mock_tgc, app, db):
    """check_mailbox_quota does not re-alert within 24h cooldown."""
    from datetime import datetime, timedelta, timezone
    from hubra.core.tasks.mail_tasks import check_mailbox_quota
    from hubra.core.models.managed_mail import ManagedMailAddress

    mock_wd = MagicMock()
    mock_wd.get_user_quota.return_value = {"allowed": 1000000, "used": 950000}
    mock_tgc.return_value = mock_wd

    mma = ManagedMailAddress(
        address="recent@hubra.club",
        address_type="mailbox",
        kind="member",
        local_part="recent",
        domain="hubra.club",
        wildduck_id="wd-recent",
        last_quota_alert_at=datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(hours=1),
    )
    db.session.add(mma)
    db.session.commit()

    result = check_mailbox_quota.run()

    assert result["alerts_sent"] == 0


@patch("hubra.core.services.wildduck.try_get_client")
def test_check_mailbox_quota_skips_no_client(mock_tgc, app, db):
    """check_mailbox_quota returns zeros when WildDuck is not configured."""
    from hubra.core.tasks.mail_tasks import check_mailbox_quota

    mock_tgc.return_value = None

    result = check_mailbox_quota.run()
    assert result == {"checked": 0, "alerts_sent": 0, "errors": 0}
