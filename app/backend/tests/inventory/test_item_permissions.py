"""Object-level inventory rights: the owner and the responsible person of an
item act on it without the club-wide inventory rights."""

import pytest

from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/inventory"
_READ = ["inventory.items.read"]


@pytest.fixture
def people(client, app, db, seeded_db):
    """Owner, responsible person and a bystander, all with read only, and an
    item (made by the admin) that the first two look after."""
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    owner = _make_role_and_member(db, tier, name="Tina", permission_keys=_READ)
    resp = _make_role_and_member(db, tier, name="Rolf", permission_keys=_READ)
    other = _make_role_and_member(db, tier, name="Otto", permission_keys=_READ)
    _login(client, "admin@test.ch")
    item = client.post(
        f"{BASE}/",
        json={
            "name": "Drill",
            "category": "Tool",
            "owner_id": owner.id,
            "responsible_id": resp.id,
        },
    ).get_json()
    return {"owner": owner, "resp": resp, "other": other, "item": item["id"]}


def _as(client, name):
    _login(client, f"{name}@test.ch")


# ── update ───────────────────────────────────────────────────────────────────


def test_owner_and_responsible_edit_their_item(client, people):
    url = f"{BASE}/{people['item']}"
    _as(client, "tina")
    assert client.patch(url, json={"location": "Shelf 2"}).status_code == 200
    _as(client, "rolf")
    r = client.patch(url, json={"status": "maintenance"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "maintenance"


def test_a_bystander_cannot_edit(client, people):
    _as(client, "otto")
    r = client.patch(f"{BASE}/{people['item']}", json={"location": "Mine now"})
    assert r.status_code == 403


def test_only_the_owner_hands_the_item_on(client, people):
    url = f"{BASE}/{people['item']}"
    _as(client, "rolf")
    for change in (
        {"owner_id": people["resp"].id},
        {"responsible_id": people["other"].id},
        {"visibility": "private"},
    ):
        r = client.patch(url, json=change)
        assert r.status_code == 403, change
        assert r.get_json()["error"] == "OWNER_ONLY"
    # The edit form sends every field back: unchanged ones pass.
    same = {
        "owner_id": people["owner"].id,
        "responsible_id": people["resp"].id,
        "visibility": "shared",
        "notes": "Oiled",
    }
    assert client.patch(url, json=same).status_code == 200

    _as(client, "tina")
    r = client.patch(url, json={"responsible_id": people["other"].id})
    assert r.status_code == 200
    # The old responsible person has lost the item.
    _as(client, "rolf")
    assert client.patch(url, json={"notes": "x"}).status_code == 403


# ── delete ───────────────────────────────────────────────────────────────────


def test_only_the_owner_deletes(client, people):
    url = f"{BASE}/{people['item']}"
    _as(client, "rolf")
    assert client.delete(url).status_code == 403
    _as(client, "otto")
    assert client.delete(url).status_code == 403
    _as(client, "tina")
    assert client.delete(url).status_code == 204


# ── instructions and checkouts ───────────────────────────────────────────────


def test_responsible_person_inducts_members(client, people):
    url = f"{BASE}/{people['item']}/instructions/{people['other'].id}"
    _as(client, "otto")
    assert client.post(url).status_code == 403
    _as(client, "rolf")
    assert client.post(url).status_code == 204
    assert client.delete(url).status_code == 204


def test_owner_lends_the_item_out_and_takes_it_back(client, people):
    item = people["item"]
    _as(client, "otto")
    body = {"member_id": people["other"].id}
    assert client.post(f"{BASE}/{item}/checkout", json=body).status_code == 403
    _as(client, "tina")
    assert client.post(f"{BASE}/{item}/checkout", json=body).status_code == 201
    _as(client, "rolf")
    assert client.post(f"{BASE}/{item}/checkin", json={}).status_code == 200


def test_role_rights_still_cover_every_item(client, app, db, seeded_db, people):
    _make_role_and_member(
        db,
        seeded_db["tier"],
        name="Keeper",
        permission_keys=_READ + ["inventory.items.update"],
    )
    _as(client, "keeper")
    r = client.patch(
        f"{BASE}/{people['item']}", json={"owner_id": people["other"].id}
    )
    assert r.status_code == 200


# ── person-owned items ───────────────────────────────────────────────────────


def test_a_person_owned_item_stays_in_the_inventory(client, people):
    """A "private" item belongs to a person, not the club: everyone
    still sees it, only the owner decides it is the club's after all."""
    url = f"{BASE}/{people['item']}"
    _as(client, "tina")
    assert client.patch(url, json={"visibility": "private"}).status_code == 200
    _as(client, "otto")
    assert "Drill" in [i["name"] for i in client.get(f"{BASE}/").get_json()]
    assert client.get(url).status_code == 200
    _as(client, "rolf")
    r = client.patch(url, json={"visibility": "shared"})
    assert r.status_code == 403


# ── adding own items ─────────────────────────────────────────────────────────


def test_sync_registers_create_own(app, db):
    from sqlalchemy import select

    from hubra.core.models.role import Permission

    app.test_cli_runner().invoke(args=["sync-permissions"])
    perm = db.session.scalar(
        select(Permission).where(Permission.key == "inventory.items.create_own")
    )
    assert perm is not None and perm.is_active


def test_add_own_item_makes_the_member_its_owner(client, app, db, seeded_db, people):
    member = _make_role_and_member(
        db,
        seeded_db["tier"],
        name="Maker",
        permission_keys=_READ + ["inventory.items.create_own"],
    )
    _as(client, "maker")
    r = client.post(
        f"{BASE}/",
        json={"name": "My saw", "category": "Tool", "owner_id": people["other"].id},
    )
    assert r.status_code == 201
    assert r.get_json()["owner_id"] == member.id
    # ... and so they may look after it.
    assert client.patch(
        f"{BASE}/{r.get_json()['id']}", json={"notes": "Sharp"}
    ).status_code == 200


def test_without_create_own_adding_stays_forbidden(client, people):
    _as(client, "otto")
    r = client.post(f"{BASE}/", json={"name": "Saw", "category": "Tool"})
    assert r.status_code == 403


# ── borrowing ────────────────────────────────────────────────────────────────


def test_an_inducted_member_borrows_a_club_item_themselves(client, people):
    item = people["item"]
    me = {"member_id": people["other"].id}
    _as(client, "otto")
    assert client.post(f"{BASE}/{item}/checkout", json=me).status_code == 403
    _as(client, "rolf")
    client.post(f"{BASE}/{item}/instructions/{people['other'].id}")
    _as(client, "otto")
    # Inducted: for themselves, not for someone else.
    other = {"member_id": people["resp"].id}
    assert client.post(f"{BASE}/{item}/checkout", json=other).status_code == 403
    assert client.post(f"{BASE}/{item}/checkout", json=me).status_code == 201


def test_induction_does_not_open_a_persons_item(client, people):
    item = people["item"]
    _as(client, "tina")
    client.patch(f"{BASE}/{item}", json={"visibility": "private"})
    client.post(f"{BASE}/{item}/instructions/{people['other'].id}")
    _as(client, "otto")
    r = client.post(f"{BASE}/{item}/checkout", json={"member_id": people["other"].id})
    assert r.status_code == 403


def test_the_borrower_brings_it_back(client, people):
    item = people["item"]
    _as(client, "tina")
    client.post(f"{BASE}/{item}/checkout", json={"member_id": people["other"].id})
    _as(client, "otto")
    assert client.post(f"{BASE}/{item}/checkin", json={}).status_code == 200


# ── person-owned items ───────────────────────────────────────────────────────


def test_not_even_an_admin_gives_away_a_persons_item(client, people):
    url = f"{BASE}/{people['item']}"
    _as(client, "tina")
    client.patch(url, json={"visibility": "private"})
    _as(client, "admin")
    for change in ({"owner_id": people["other"].id}, {"visibility": "shared"}):
        r = client.patch(url, json=change)
        assert r.status_code == 403, change
        assert r.get_json()["error"] == "PERSON_OWNED"
    assert client.delete(url).status_code == 403
    # Looking after it stays the club's business.
    r = client.patch(url, json={"responsible_id": people["other"].id, "status": "broken"})
    assert r.status_code == 200
    _as(client, "tina")
    assert client.delete(url).status_code == 204


def test_once_the_owner_left_the_club_decides(client, db, people):
    from datetime import datetime, timezone

    url = f"{BASE}/{people['item']}"
    _as(client, "tina")
    client.patch(url, json={"visibility": "private"})
    people["owner"].archived_at = datetime.now(timezone.utc)
    db.session.commit()
    _as(client, "admin")
    assert client.delete(url).status_code == 204
