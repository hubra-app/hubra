"""Tests for Function API — CRUD, holder assignment, deletion blocking."""

from unittest import mock
from unittest.mock import MagicMock, patch

from vollbuild.core.extensions import db
from vollbuild.core.models.function import Function, FunctionHolder
from vollbuild.core.models.managed_mail import ManagedMailAddress


# ── CRUD ──────────────────────────────────────────────────────────────────────


def test_list_functions_empty(client, seeded_db, auth_headers):
    resp = client.get("/api/v1/functions/", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_function(client, seeded_db, auth_headers):
    resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier", "description": "Treasurer", "maxHolders": 1},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Kassier"
    assert body["maxHolders"] == 1


def test_create_function_duplicate_name(client, seeded_db, auth_headers):
    client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier"},
    )
    resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier"},
    )
    assert resp.status_code == 409


def test_update_function(client, seeded_db, auth_headers):
    create_resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier", "maxHolders": 1},
    )
    fn_id = create_resp.get_json()["id"]

    resp = client.patch(
        f"/api/v1/functions/{fn_id}",
        headers=auth_headers,
        json={"description": "Updated description", "maxHolders": 2},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["description"] == "Updated description"
    assert body["maxHolders"] == 2


def test_update_function_max_holders_below_current(client, seeded_db, auth_headers):
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User

    create_resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier", "maxHolders": 2},
    )
    fn_id = create_resp.get_json()["id"]

    m1 = seeded_db["admin"]
    tier = seeded_db["tier"]
    user2 = User(
        email="second@test.ch",
        first_name="Second",
        last_name="Person",
    )
    user2.set_password("password123")
    db.session.add(user2)
    db.session.flush()

    m2 = Member(
        user_id=user2.id,
        status="active",
        tier_id=tier.id,
    )
    db.session.add(m2)
    db.session.flush()

    db.session.add(FunctionHolder(function_id=fn_id, member_id=m1.id))
    db.session.add(FunctionHolder(function_id=fn_id, member_id=m2.id))
    db.session.commit()

    resp = client.patch(
        f"/api/v1/functions/{fn_id}",
        headers=auth_headers,
        json={"maxHolders": 1},
    )
    assert resp.status_code == 400


def test_delete_function(client, seeded_db, auth_headers):
    create_resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "TempFunction"},
    )
    fn_id = create_resp.get_json()["id"]

    resp = client.delete(f"/api/v1/functions/{fn_id}", headers=auth_headers)
    assert resp.status_code == 200

    assert db.session.get(Function, fn_id) is None


def test_delete_function_with_protected_mma(client, seeded_db, auth_headers):
    """Function with a protected MMA can be deleted — MMA is cleaned up automatically."""
    from vollbuild.api.settings.service import SettingsService

    fn = Function(name="ProtectedFn")
    db.session.add(fn)
    db.session.flush()

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"protectedfn@{domain}",
        address_type="alias",
        is_protected=True,
        owner_type="function",
        owner_id=fn.id,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.delete(f"/api/v1/functions/{fn.id}", headers=auth_headers)
    assert resp.status_code == 200


# ── Holder management ─────────────────────────────────────────────────────────


def test_assign_holder(client, seeded_db, auth_headers):
    create_resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "Kassier", "maxHolders": 1},
    )
    fn_id = create_resp.get_json()["id"]
    member_id = seeded_db["admin"].id

    resp = client.post(
        f"/api/v1/functions/{fn_id}/holders",
        headers=auth_headers,
        json={"memberId": member_id},
    )
    assert resp.status_code == 201

    fn = db.session.get(Function, fn_id)
    assert len(fn.holders) == 1
    assert fn.holders[0].member_id == member_id


def test_assign_holder_exceeds_max(client, seeded_db, auth_headers):
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User

    tier = seeded_db["tier"]
    fn = Function(name="SingleOffice", max_holders=1)
    db.session.add(fn)
    db.session.flush()

    m1 = seeded_db["admin"]
    user2 = User(
        email="second@test.ch",
        first_name="Second",
        last_name="Person",
    )
    user2.set_password("password123")
    db.session.add(user2)
    db.session.flush()

    m2 = Member(
        user_id=user2.id,
        status="active",
        tier_id=tier.id,
    )
    db.session.add(m2)
    db.session.flush()

    db.session.add(FunctionHolder(function_id=fn.id, member_id=m1.id))
    db.session.commit()

    resp = client.post(
        f"/api/v1/functions/{fn.id}/holders",
        headers=auth_headers,
        json={"memberId": m2.id},
    )
    assert resp.status_code == 409


def test_assign_duplicate_holder(client, seeded_db, auth_headers):
    member = seeded_db["admin"]
    fn = Function(name="Kassier", max_holders=2)
    db.session.add(fn)
    db.session.flush()
    db.session.add(FunctionHolder(function_id=fn.id, member_id=member.id))
    db.session.commit()

    resp = client.post(
        f"/api/v1/functions/{fn.id}/holders",
        headers=auth_headers,
        json={"memberId": member.id},
    )
    assert resp.status_code == 409


def test_remove_holder(client, seeded_db, auth_headers):
    member = seeded_db["admin"]
    fn = Function(name="Kassier", max_holders=1)
    db.session.add(fn)
    db.session.flush()
    db.session.add(FunctionHolder(function_id=fn.id, member_id=member.id))
    db.session.commit()

    resp = client.delete(
        f"/api/v1/functions/{fn.id}/holders/{member.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    fn = db.session.get(Function, fn.id)
    assert len(fn.holders) == 0


def test_assign_holder_triggers_mail_sync(client, seeded_db, auth_headers):
    fn = Function(name="Kassier", max_holders=1)
    db.session.add(fn)
    db.session.flush()

    from vollbuild.api.settings.service import SettingsService

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"kassier@{domain}",
        address_type="mailbox",
        is_protected=True,
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
    )
    db.session.add(addr)
    db.session.commit()

    with mock.patch(
        "vollbuild.core.tasks.mail_tasks.reconcile_entity_forwarding_task"
    ) as mock_task:
        mock_task.delay = mock.MagicMock()
        resp = client.post(
            f"/api/v1/functions/{fn.id}/holders",
            headers=auth_headers,
            json={"memberId": seeded_db["admin"].id},
        )
        assert resp.status_code == 201
        mock_task.delay.assert_called_once_with("function", fn.id)


# ── Function mail MMA endpoints ───────────────────────────────────────────────


def test_create_function_mail(client, seeded_db, auth_headers):
    from vollbuild.core.models.setting import Setting

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    create_resp = client.post(
        "/api/v1/functions/",
        headers=auth_headers,
        json={"name": "TestFn"},
    )
    fn_id = create_resp.get_json()["id"]

    # Function auto-creates a disabled MMA — POST should return 409
    resp = client.post(
        f"/api/v1/mail/functions/{fn_id}",
        headers=auth_headers,
        json={"prefix": "testfn"},
    )
    assert resp.status_code == 409

    # Verify auto-created MMA exists
    addrs = db.session.scalars(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == fn_id,
        )
    ).all()
    assert len(addrs) >= 1
    assert addrs[0].kind == "function"


def test_list_function_mail(client, seeded_db, auth_headers):
    from vollbuild.api.settings.service import SettingsService

    fn = Function(name="ListFn")
    db.session.add(fn)
    db.session.flush()

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"listfn@{domain}",
        address_type="mailbox",
        is_protected=True,
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.get("/api/v1/mail/functions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert any(a["linkedFunctionId"] == fn.id for a in data)


def test_delete_function_mail_blocked(client, seeded_db, auth_headers):
    """DELETE /mail/functions/<id> returns 409 while the function exists."""
    from vollbuild.api.settings.service import SettingsService

    fn = Function(name="DelFn")
    db.session.add(fn)
    db.session.flush()

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"delfn@{domain}",
        address_type="mailbox",
        is_protected=True,
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.delete(f"/api/v1/mail/functions/{fn.id}", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json().get("error") == "MMA_LOCKED_TO_OWNER"

    # Verify MMA was NOT deleted
    remaining = db.session.scalars(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == fn.id,
        )
    ).all()
    assert len(remaining) == 1


# ── Group protected deletion ──────────────────────────────────────────────────


def test_delete_group_with_protected_mma(client, seeded_db, auth_headers):
    """Group with a protected MMA can be deleted — MMA is cleaned up automatically."""
    from vollbuild.core.models.group import Group

    group = Group(name="ProtectedGroup")
    db.session.add(group)
    db.session.flush()

    from vollbuild.api.settings.service import SettingsService

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"protectedgroup@{domain}",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.delete(f"/api/v1/groups/{group.id}", headers=auth_headers)
    assert resp.status_code == 204


# ── Seed idempotency ──────────────────────────────────────────────────────────


def test_seed_creates_vorstand_and_functions(db):
    from vollbuild.core.seeds import run_seeds

    run_seeds(db)

    from vollbuild.core.models.group import Group
    from vollbuild.core.models.function import Function

    vorstand = db.session.scalar(db.select(Group).where(Group.name == "Vorstand"))
    assert vorstand is not None
    assert vorstand.is_default is True

    for name in ("Kassier", "Präsidium", "Aktuar"):
        fn = db.session.scalar(db.select(Function).where(Function.name == name))
        assert fn is not None
        assert fn.max_holders == 1


def test_seed_creates_managed_mail_addresses(db):
    from vollbuild.core.seeds import run_seeds

    run_seeds(db)

    from vollbuild.api.settings.service import SettingsService

    domain = SettingsService().get("mail.domain") or "vollbuild.ch"

    for prefix in (
        "noreply",
        "postmaster",
        "vorstand",
        "kassier",
        "praesidium",
        "aktuar",
    ):
        addr = db.session.scalar(
            db.select(ManagedMailAddress).where(
                ManagedMailAddress.address == f"{prefix}@{domain}"
            )
        )
        assert addr is not None, f"Missing managed mail address: {prefix}@{domain}"
        assert addr.is_protected is True


def test_seed_is_idempotent(db):
    from vollbuild.core.seeds import run_seeds

    run_seeds(db)
    count_before = db.session.scalar(
        db.select(db.func.count()).select_from(ManagedMailAddress)
    )

    run_seeds(db)
    count_after = db.session.scalar(
        db.select(db.func.count()).select_from(ManagedMailAddress)
    )

    assert count_before == count_after


# ── Target resolution ─────────────────────────────────────────────────────────


def test_resolve_alias_targets_group_members(db, seeded_db):
    from vollbuild.core.services.managed_mail import resolve_alias_targets
    from vollbuild.core.models.group import Group

    group = Group(name="TestGroup")
    db.session.add(group)
    db.session.flush()

    member = seeded_db["admin"]
    member.public_email = "admin@vollbuild.ch"
    db.session.execute(
        db.text("INSERT INTO member_groups (member_id, group_id) VALUES (:mid, :gid)"),
        {"mid": member.id, "gid": group.id},
    )

    from vollbuild.api.settings.service import SettingsService

    domain = SettingsService().get("mail.domain") or "test.ch"
    addr = ManagedMailAddress(
        address=f"testgroup@{domain}",
        address_type="alias",
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()

    targets = resolve_alias_targets(addr)
    assert "admin@vollbuild.ch" in targets


def test_resolve_alias_targets_empty_falls_back_to_postmaster(db, seeded_db):
    from vollbuild.core.services.managed_mail import resolve_alias_targets
    from vollbuild.core.models.setting import Setting

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    domain = "test.ch"
    addr = ManagedMailAddress(
        address=f"somefn@{domain}",
        address_type="alias",
        owner_type="function",
        owner_id=999,
    )
    db.session.add(addr)
    db.session.commit()

    targets = resolve_alias_targets(addr)
    assert f"postmaster@{domain}" in targets


# ── Function mail hub-pattern tests ───────────────────────────────────────────


def _make_function_mma(db, fn, *, domain="club.ch", **overrides):
    """Helper: create a mailbox-type function MMA."""
    defaults = dict(
        address=f"{fn.name.lower()}@{domain}",
        address_type="mailbox",
        is_protected=True,
        is_enabled=True,
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
        local_part=fn.name.lower(),
        domain=domain,
        provisioning_status="provisioned",
        wildduck_id="wd-fn-001",
    )
    defaults.update(overrides)
    addr = ManagedMailAddress(**defaults)
    db.session.add(addr)
    db.session.flush()
    return addr


def test_reassign_holder_repoints_forwarding(app, db, seeded_db):
    """reconcile_entity_forwarding for function calls ensure_forwarding with new holder's email."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User

    fn = Function(name="ReassignFn", max_holders=1)
    db.session.add(fn)
    db.session.flush()

    member_a = db.session.get(Member, seeded_db["admin"].id)
    member_a.public_email = "a@example.ch"

    holder = FunctionHolder(function_id=fn.id, member_id=member_a.id)
    db.session.add(holder)
    db.session.flush()

    _make_function_mma(db, fn)
    db.session.commit()

    from vollbuild.core.services.mail_provisioning import reconcile_entity_forwarding

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_tgc.return_value = MagicMock()
        with patch(
            "vollbuild.core.services.mail_provisioning.ensure_forwarding"
        ) as mock_fwd:
            reconcile_entity_forwarding("function", fn.id)
            called_targets = mock_fwd.call_args[0][1]
            assert "a@example.ch" in called_targets

    db.session.delete(holder)
    user_b = User(
        email="b@example.ch",
        first_name="Bob",
        last_name="Test",
    )
    user_b.set_password("password123")
    db.session.add(user_b)
    db.session.flush()

    member_b = Member(
        user_id=user_b.id,
        public_email="b@example.ch",
        status="active",
        tier_id=1,
    )
    db.session.add(member_b)
    db.session.flush()
    holder_b = FunctionHolder(function_id=fn.id, member_id=member_b.id)
    db.session.add(holder_b)
    db.session.commit()

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_tgc.return_value = MagicMock()
        with patch(
            "vollbuild.core.services.mail_provisioning.ensure_forwarding"
        ) as mock_fwd:
            reconcile_entity_forwarding("function", fn.id)
            called_targets = mock_fwd.call_args[0][1]
            assert "b@example.ch" in called_targets
            assert "a@example.ch" not in called_targets


def test_function_two_holders_both_forward(app, db, seeded_db):
    """Function with max_holders=2 and two holders forwards to both."""
    from vollbuild.core.models.member import Member
    from vollbuild.core.models.user import User

    fn = Function(name="DualFn", max_holders=2)
    db.session.add(fn)
    db.session.flush()

    m1 = db.session.get(Member, seeded_db["admin"].id)
    m1.public_email = "first@example.ch"

    user2 = User(
        email="second@example.ch",
        first_name="Second",
        last_name="Holder",
    )
    user2.set_password("password123")
    db.session.add(user2)
    db.session.flush()

    m2 = Member(
        user_id=user2.id,
        public_email="second@example.ch",
        status="active",
        tier_id=1,
    )
    db.session.add(m2)
    db.session.flush()

    db.session.add(FunctionHolder(function_id=fn.id, member_id=m1.id))
    db.session.add(FunctionHolder(function_id=fn.id, member_id=m2.id))
    db.session.flush()

    _make_function_mma(db, fn)
    db.session.commit()

    from vollbuild.core.services.mail_provisioning import reconcile_entity_forwarding

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_tgc.return_value = MagicMock()
        with patch(
            "vollbuild.core.services.mail_provisioning.ensure_forwarding"
        ) as mock_fwd:
            reconcile_entity_forwarding("function", fn.id)
            called_targets = mock_fwd.call_args[0][1]
            assert "first@example.ch" in called_targets
            assert "second@example.ch" in called_targets


def test_additional_function_alias_forwards_to_primary(app, db, seeded_db):
    """Additional function alias resolves targets to [primary.address]."""
    fn = Function(name="AliasFn")
    db.session.add(fn)
    db.session.flush()

    _make_function_mma(db, fn, address="aliasfn@club.ch")

    extra = ManagedMailAddress(
        address="aliasfn-extra@club.ch",
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        owner_type="function",
        owner_id=fn.id,
        kind="function",
        enabled=True,
        local_part="aliasfn-extra",
        domain="club.ch",
    )
    db.session.add(extra)
    db.session.commit()

    from vollbuild.core.services.mail_provisioning import (
        _resolve_function_alias_targets,
    )

    targets = _resolve_function_alias_targets(extra)
    assert targets == ["aliasfn@club.ch"]


def test_disable_function_mail_ensure_absent(client, db, seeded_db, auth_headers):
    """Toggling function mail off calls ensure_absent."""
    fn = Function(name="DisableFn")
    db.session.add(fn)
    db.session.commit()

    addr = _make_function_mma(
        db,
        fn,
        address="disablefn@club.ch",
        is_enabled=True,
        enabled=True,
        wildduck_id="wd-user-001",
    )
    db.session.commit()

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_wd = MagicMock()
        mock_tgc.return_value = mock_wd
        resp = client.patch(
            f"/api/v1/mail/functions/{fn.id}/toggle",
            json={"enabled": False},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    db.session.refresh(addr)
    assert addr.is_enabled is False
    assert addr.enabled is False
    mock_wd.safe_delete_user.assert_called_once_with("wd-user-001")


def test_function_prefix_edit_moves_address(client, db, seeded_db, auth_headers):
    """Changing prefix ensures_absent old address then provisions new."""
    fn = Function(name="PrefixFn")
    db.session.add(fn)
    db.session.flush()

    addr = _make_function_mma(
        db,
        fn,
        address="prefixfn@club.ch",
        local_part="prefixfn",
        domain="club.ch",
        wildduck_id="wd-user-001",
    )
    db.session.commit()

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_wd = MagicMock()
        mock_wd.safe_get_user.return_value = {"id": "wd-user-001"}
        mock_wd.create_user.return_value = {"id": "wd-user-002"}
        mock_wd.list_user_addresses.return_value = {"results": []}
        mock_tgc.return_value = mock_wd
        with patch(
            "vollbuild.api.settings.service.SettingsService.get",
            return_value="club.ch",
        ):
            resp = client.patch(
                f"/api/v1/mail/functions/{fn.id}/prefix",
                json={"prefix": "newprefix"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    db.session.refresh(addr)
    assert addr.address == "newprefix@club.ch"
    assert addr.local_part == "newprefix"
    mock_wd.safe_delete_user.assert_called_once_with("wd-user-001")


def test_function_prefix_collision_auto_suffix(app, db, seeded_db):
    """resolve_local_part suffixes on collision."""
    fn1 = Function(name="CollideFn")
    db.session.add(fn1)
    db.session.flush()
    _make_function_mma(
        db, fn1, address="collidefn@club.ch", local_part="collidefn", domain="club.ch"
    )
    db.session.commit()

    fn2 = Function(name="CollideFn2")
    db.session.add(fn2)
    db.session.flush()
    db.session.commit()

    from vollbuild.core.services.managed_mail import get_or_create_for_function

    with patch(
        "vollbuild.core.services.mail_provisioning._get_club_domain",
        return_value="club.ch",
    ):
        addr = get_or_create_for_function(fn2.id, "collidefn", "club.ch")
        assert addr.local_part != "collidefn"
        assert addr.local_part.startswith("collidefn")


def test_reconcile_mail_provisions_unprovisioned_function_mma(app, db, seeded_db):
    """reconcile_mail provisions a function MMA with no wildduck_id."""
    fn = Function(name="UnprovFn")
    db.session.add(fn)
    db.session.flush()

    addr = _make_function_mma(
        db,
        fn,
        address="unprovfn@club.ch",
        wildduck_id=None,
        provisioning_status="pending",
    )
    db.session.commit()

    from vollbuild.core.tasks.mail_tasks import reconcile_mail

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_wd = MagicMock()
        mock_wd.create_user.return_value = {"id": "wd-new-001"}
        mock_wd.list_user_addresses.return_value = {"results": []}
        mock_tgc.return_value = mock_wd
        with patch(
            "vollbuild.core.services.mail_provisioning._resolve_function_holder_targets",
            return_value=["target@example.ch"],
        ):
            reconcile_mail.run()

    db.session.refresh(addr)
    assert addr.wildduck_id == "wd-new-001"
    assert addr.sync_state == "ok"


def test_reconcile_mail_skips_disabled_function_mma(app, db, seeded_db):
    """reconcile_mail calls ensure_absent for disabled function MMA."""
    fn = Function(name="DisabledFn")
    db.session.add(fn)
    db.session.flush()

    addr = _make_function_mma(
        db,
        fn,
        address="disabledfn@club.ch",
        is_enabled=False,
        enabled=False,
        wildduck_id="wd-user-001",
    )
    db.session.commit()

    from vollbuild.core.tasks.mail_tasks import reconcile_mail

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_wd = MagicMock()
        mock_tgc.return_value = mock_wd
        reconcile_mail.run()

    db.session.refresh(addr)
    assert addr.wildduck_id is None
    mock_wd.safe_delete_user.assert_called_once_with("wd-user-001")


def test_reconcile_mail_auto_creates_missing_mma(app, db, seeded_db):
    """reconcile_mail auto-creates a disabled MMA for a group/function with no MMA."""
    from vollbuild.core.models.group import Group
    from vollbuild.core.models.setting import Setting
    from vollbuild.core.tasks.mail_tasks import reconcile_mail

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    group = Group(name="AutoCreateGroup")
    db.session.add(group)
    db.session.flush()
    group_id = group.id
    db.session.commit()

    existing = db.session.scalar(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
        )
    )
    assert existing is None

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_tgc.return_value = None
        result = reconcile_mail.run()

    mma = db.session.scalar(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
        )
    )
    assert mma is not None
    assert mma.enabled is False
    assert mma.address_type == "alias"
    assert mma.is_protected is True
    assert result["created"] >= 1


def test_reconcile_mail_removes_orphaned_mma(app, db, seeded_db):
    """reconcile_mail removes an MMA whose owner no longer exists."""
    from vollbuild.core.models.setting import Setting
    from vollbuild.core.tasks.mail_tasks import reconcile_mail

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    orphan = ManagedMailAddress(
        address="orphan@test.ch",
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        mail_prefix="orphan",
        kind="group",
        local_part="orphan",
        domain="test.ch",
        owner_type="group",
        owner_id=999999,
        enabled=True,
    )
    db.session.add(orphan)
    db.session.commit()
    orphan_id = orphan.id

    with patch("vollbuild.core.services.mail_provisioning.try_get_client") as mock_tgc:
        mock_tgc.return_value = None
        with patch("vollbuild.core.services.mail_provisioning.ensure_absent"):
            result = reconcile_mail.run()

    deleted = db.session.get(ManagedMailAddress, orphan_id)
    assert deleted is None
    assert result["removed"] >= 1


def test_group_service_create_auto_creates_disabled_mma(app, db, seeded_db):
    """GroupsService.create auto-creates a disabled MMA for the new group."""
    from vollbuild.core.models.setting import Setting
    from vollbuild.api.groups.services import GroupsService

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    group = GroupsService.create({"name": "AutoMMA"}, actor_id=1)
    db.session.commit()

    mma = db.session.scalar(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group.id,
        )
    )
    assert mma is not None
    assert mma.enabled is False
    assert mma.address_type == "alias"


def test_function_service_create_auto_creates_disabled_mma(app, db, seeded_db):
    """FunctionService.create auto-creates a disabled MMA for the new function."""
    from vollbuild.core.models.setting import Setting
    from vollbuild.api.functions.services import FunctionService

    db.session.add(Setting(key="mail.domain", value="test.ch"))
    db.session.commit()

    fn = FunctionService.create(name="AutoMMAFn", description="Test")
    db.session.commit()

    mma = db.session.scalar(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == fn.id,
        )
    )
    assert mma is not None
    assert mma.enabled is False
    assert mma.address_type == "alias"
