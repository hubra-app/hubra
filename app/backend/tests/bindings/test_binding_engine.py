"""Tests for the binding engine — sync, scalar guard, array dedup,
protected bindings, validation, write-only attributes, delete guards."""

import pytest

from vollbuild.crypto import decrypt_code
from vollbuild.extensions import db
from vollbuild.core.models.binding import Binding
from vollbuild.core.models.internal_key import InternalKey
from vollbuild.core.models.member import Member
from vollbuild.core.models.setting import Setting
from vollbuild.core.models.user import User
from vollbuild.core.services.binding_engine import (
    assert_source_deletable,
    cascade_delete_disabled,
    check_source_delete_blocked,
    create_binding,
    delete_binding,
    sync_for_source,
    toggle_binding,
    update_binding,
)
from vollbuild.core.services.key_service import KeyService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_key(db, key="test.key", allow_multiple=False, is_protected=False, label=None):
    ik = InternalKey(
        key=key,
        allow_multiple=allow_multiple,
        is_protected=is_protected,
        label=label,
    )
    db.session.add(ik)
    db.session.flush()
    return ik


def _make_member(db, name="Test Member", email="test@example.ch", public_email=None):
    parts = name.split()
    user = User(email=email, first_name=parts[0], last_name=parts[-1])
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    m = Member(user_id=user.id)
    if public_email:
        m.public_email = public_email
    db.session.add(m)
    db.session.flush()
    return m


def _get_ik_value(ik):
    db.session.refresh(ik)
    if ik.value is None:
        return None
    return decrypt_code(ik.value)


# ── 1. Scalar key sync ────────────────────────────────────────────────────────


def test_scalar_key_writes_value(db):
    ik = _make_key(db, "test.scalar")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
    )
    db.session.commit()
    assert _get_ik_value(ik) == "Alice Smith"


def test_scalar_key_clears_on_disable(db):
    ik = _make_key(db, "test.scalar")
    m = _make_member(db, "Bob Jones", "bob@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
    )
    db.session.commit()
    assert _get_ik_value(ik) == "Bob Jones"

    toggle_binding(b.id, False)
    db.session.commit()
    assert _get_ik_value(ik) is None


def test_scalar_key_updates_on_source_change(db):
    ik = _make_key(db, "test.scalar")
    m = _make_member(db, "Carol White", "carol@example.ch")
    create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
    )
    db.session.commit()
    assert _get_ik_value(ik) == "Carol White"

    m.user.last_name = "Changed"
    sync_for_source("member", str(m.id))
    db.session.commit()
    assert _get_ik_value(ik) == "Carol Changed"


# ── 2. Scalar guard ───────────────────────────────────────────────────────────


def test_scalar_rejects_second_enabled(db):
    ik = _make_key(db, "test.scalar")
    m1 = _make_member(db, "Alice Smith", "alice@example.ch")
    m2 = _make_member(db, "Bob Jones", "bob@example.ch")
    create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    db.session.flush()
    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        create_binding(
            type="member",
            source_id=str(m2.id),
            source_attribute="name",
            key_id=ik.id,
        )
    assert exc_info.value.status == 409
    assert "SCALAR_KEY_OCCUPIED" in exc_info.value.code


def test_scalar_allows_disabled_second(db):
    ik = _make_key(db, "test.scalar")
    m1 = _make_member(db, "Alice Smith", "alice@example.ch")
    m2 = _make_member(db, "Bob Jones", "bob@example.ch")
    create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    db.session.flush()
    b2 = create_binding(
        type="member",
        source_id=str(m2.id),
        source_attribute="name",
        key_id=ik.id,
        enabled=False,
    )
    db.session.commit()
    assert b2.enabled is False
    assert _get_ik_value(ik) == "Alice Smith"


# ── 3. Array key dedup + stable order ────────────────────────────────────────


def test_array_key_builds_list(db):
    ik = _make_key(db, "test.array", allow_multiple=True)
    m1 = _make_member(db, "Alice Smith", "alice@example.ch")
    m2 = _make_member(db, "Bob Jones", "bob@example.ch")
    create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    create_binding(
        type="member", source_id=str(m2.id), source_attribute="name", key_id=ik.id
    )
    db.session.commit()
    val = KeyService.get("test.array")
    assert val == ["Alice Smith", "Bob Jones"]


def test_array_key_dedup(db):
    ik = _make_key(db, "test.array", allow_multiple=True)
    m1 = _make_member(db, "Dup Name", "a@example.ch")
    m2 = _make_member(db, "Dup Name", "b@example.ch")
    create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    create_binding(
        type="member", source_id=str(m2.id), source_attribute="name", key_id=ik.id
    )
    db.session.commit()
    val = KeyService.get("test.array")
    assert val == ["Dup Name"]


def test_array_key_stable_order_by_id(db):
    ik = _make_key(db, "test.array", allow_multiple=True)
    m1 = _make_member(db, "Zara Zara", "z@example.ch")
    m2 = _make_member(db, "Anna Anna", "a2@example.ch")
    b1 = create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    b2 = create_binding(
        type="member", source_id=str(m2.id), source_attribute="name", key_id=ik.id
    )
    db.session.commit()
    assert b1.id < b2.id
    val = KeyService.get("test.array")
    assert val == ["Zara Zara", "Anna Anna"]


def test_array_key_removes_on_disable(db):
    ik = _make_key(db, "test.array", allow_multiple=True)
    m1 = _make_member(db, "Alice Smith", "alice@example.ch")
    m2 = _make_member(db, "Bob Jones", "bob@example.ch")
    b1 = create_binding(
        type="member", source_id=str(m1.id), source_attribute="name", key_id=ik.id
    )
    create_binding(
        type="member", source_id=str(m2.id), source_attribute="name", key_id=ik.id
    )
    db.session.commit()
    assert KeyService.get("test.array") == ["Alice Smith", "Bob Jones"]

    toggle_binding(b1.id, False)
    db.session.commit()
    assert KeyService.get("test.array") == ["Bob Jones"]


# ── 4. Protected binding ─────────────────────────────────────────────────────


def test_protected_cannot_delete(db):
    ik = _make_key(db, "test.protected", is_protected=True)
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
        is_protected=True,
    )
    db.session.flush()
    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        delete_binding(b.id)
    assert exc_info.value.status == 409
    assert "PROTECTED" in exc_info.value.code


def test_protected_cannot_toggle(db):
    ik = _make_key(db, "test.protected", is_protected=True)
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
        is_protected=True,
    )
    db.session.flush()
    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        toggle_binding(b.id, False)
    assert exc_info.value.status == 409
    assert "PROTECTED" in exc_info.value.code


def test_protected_cannot_change_key(db):
    ik1 = _make_key(db, "test.protected1", is_protected=True)
    ik2 = _make_key(db, "test.protected2")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik1.id,
        is_protected=True,
    )
    db.session.flush()
    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        update_binding(b.id, key_id=ik2.id)
    assert exc_info.value.status == 409
    assert "PROTECTED" in exc_info.value.code


def test_protected_can_edit_validator(db):
    ik = _make_key(db, "test.protected", is_protected=True)
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
        is_protected=True,
        validator="none",
    )
    db.session.flush()
    updated = update_binding(b.id, validator="non_empty")
    db.session.commit()
    assert updated.validator == "non_empty"


# ── 5. Validation failures ───────────────────────────────────────────────────


def test_validation_failure_skips_write(db):
    ik = _make_key(db, "test.val")
    m = _make_member(
        db, "Not Email", "notemail@example.ch", public_email="not-an-email"
    )
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="primary_mail_address",
        key_id=ik.id,
        validator="email",
    )
    db.session.commit()
    assert _get_ik_value(ik) is None
    assert b.validation_status == "failed"
    assert b.validation_error is not None


def test_validation_success_writes_value(db):
    ik = _make_key(db, "test.val")
    m = _make_member(
        db, "Alice Smith", "alice@example.ch", public_email="alice@example.ch"
    )
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="primary_mail_address",
        key_id=ik.id,
        validator="email",
    )
    db.session.commit()
    assert _get_ik_value(ik) == "alice@example.ch"
    assert b.validation_status == "ok"


# ── 6. Write-only attributes (password) ──────────────────────────────────────


def test_write_only_skips_write_no_failure(db):
    ik = _make_key(db, "test.writeonly")
    _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="mail_address",
        source_id="999",
        source_attribute="password",
        key_id=ik.id,
    )
    db.session.commit()
    assert _get_ik_value(ik) is None
    assert b.validation_status == "ok"
    assert b.validation_error is None


# ── 7. Delete guards ─────────────────────────────────────────────────────────


def test_enabled_binding_blocks_source_delete(db):
    ik = _make_key(db, "test.guard")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    create_binding(
        type="member", source_id=str(m.id), source_attribute="name", key_id=ik.id
    )
    db.session.flush()
    blocked = check_source_delete_blocked("member", str(m.id))
    assert len(blocked) == 1

    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        assert_source_deletable("member", str(m.id))
    assert exc_info.value.status == 409


def test_disabled_binding_does_not_block(db):
    ik = _make_key(db, "test.guard")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
        enabled=False,
    )
    db.session.flush()
    blocked = check_source_delete_blocked("member", str(m.id))
    assert len(blocked) == 0


def test_cascade_delete_disabled(db):
    ik = _make_key(db, "test.cascade")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    b = create_binding(
        type="member",
        source_id=str(m.id),
        source_attribute="name",
        key_id=ik.id,
        enabled=False,
    )
    db.session.flush()
    cascade_delete_disabled("member", str(m.id))
    db.session.commit()
    assert db.session.get(Binding, b.id) is None


# ── 8. Setting source binding ────────────────────────────────────────────────


def test_setting_binding_syncs_on_change(db):
    db.session.add(Setting(key="club.name", value="Old Name"))
    db.session.flush()

    ik = _make_key(db, "test.setting")
    create_binding(
        type="setting",
        source_id="club.name",
        source_attribute="value",
        key_id=ik.id,
    )
    db.session.commit()
    assert _get_ik_value(ik) == "Old Name"

    setting = db.session.get(Setting, "club.name")
    setting.value = "New Name"
    db.session.flush()
    sync_for_source("setting", "club.name")
    db.session.commit()
    assert _get_ik_value(ik) == "New Name"


# ── 9. Duplicate binding rejection ───────────────────────────────────────────


def test_duplicate_binding_rejected(db):
    ik = _make_key(db, "test.dup")
    m = _make_member(db, "Alice Smith", "alice@example.ch")
    create_binding(
        type="member", source_id=str(m.id), source_attribute="name", key_id=ik.id
    )
    db.session.flush()
    from vollbuild.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        create_binding(
            type="member",
            source_id=str(m.id),
            source_attribute="name",
            key_id=ik.id,
        )
    assert exc_info.value.status == 409
    assert "CONFLICT" in exc_info.value.code


# ── 10. KeyService get/set/delete ────────────────────────────────────────────


def test_key_service_set_get_scalar(db):
    _make_key(db, "ks.scalar")
    KeyService.set("ks.scalar", "hello")
    db.session.commit()
    assert KeyService.get("ks.scalar") == "hello"


def test_key_service_set_get_array(db):
    _make_key(db, "ks.array", allow_multiple=True)
    KeyService.set("ks.array", ["a", "b", "c"])
    db.session.commit()
    assert KeyService.get("ks.array") == ["a", "b", "c"]


def test_key_service_delete(db):
    _make_key(db, "ks.del")
    KeyService.set("ks.del", "temp")
    db.session.commit()
    assert KeyService.get("ks.del") == "temp"
    KeyService.delete("ks.del")
    db.session.commit()
    assert KeyService.get("ks.del") is None


def test_key_service_get_missing_key_returns_none(db):
    assert KeyService.get("nonexistent.key") is None
