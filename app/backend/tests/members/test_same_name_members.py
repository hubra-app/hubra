"""Two people with the same name can join one club."""

from unittest.mock import patch

from tests.helpers import add_member, patch_mail_domain


def test_same_name_gets_a_numbered_username(client, auth_headers, seeded_db):
    first = add_member(
        client, auth_headers, email="anna1@test.ch", first_name="Anna", last_name="Muster"
    )
    second = add_member(
        client, auth_headers, email="anna2@test.ch", first_name="Anna", last_name="Muster"
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["club_username"] == "anna.muster"
    assert second.get_json()["club_username"] == "anna.muster2"


def test_same_name_gets_a_numbered_club_address(client, auth_headers, seeded_db):
    with (
        patch_mail_domain("club.ch"),
        # No mail server here: keep the mailbox step out of it.
        patch("hubra.api.members.services._provision_member_mailbox"),
    ):
        emails = [
            add_member(
                client,
                auth_headers,
                email=f"max{i}@test.ch",
                first_name="Max",
                last_name="Müller",
            ).get_json()["public_email"]
            for i in range(3)
        ]
    assert emails == [
        "max.mueller@club.ch",
        "max.mueller2@club.ch",
        "max.mueller3@club.ch",
    ]


def test_a_failed_club_address_does_not_lose_the_member(client, auth_headers, seeded_db):
    with (
        patch_mail_domain("club.ch"),
        patch(
            "hubra.core.services.managed_mail.get_or_create_for_member",
            side_effect=RuntimeError("address taken"),
        ),
    ):
        resp = add_member(client, auth_headers, email="eva@test.ch", first_name="Eva")
    assert resp.status_code == 200
    member_id = resp.get_json()["id"]
    assert client.get(f"/api/v1/members/{member_id}", headers=auth_headers).status_code == 200


def test_a_new_username_that_is_taken_shows_the_address_they_got(
    client, auth_headers, seeded_db, db
):
    """A username whose address a group already has gets a numbered one; the
    member's club address must show that one, not the group's."""
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.models.member import Member

    anna = db.session.get(Member, seeded_db["admin"].id)
    common = {"is_enabled": False, "domain": "club.ch", "address_type": "alias"}
    db.session.add_all(
        [
            ManagedMailAddress(
                address="vorstand@club.ch",
                local_part="vorstand",
                kind="group",
                owner_type="group",
                owner_id=1,
                **common,
            ),
            ManagedMailAddress(
                address="test.admin@club.ch",
                local_part="test.admin",
                kind="member",
                owner_type="member",
                owner_id=anna.id,
                **common,
            ),
        ]
    )
    db.session.commit()

    with patch_mail_domain("club.ch"):
        resp = client.patch(
            f"/api/v1/members/{anna.id}",
            json={"club_username": "vorstand"},
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.get_json()
    mma = db.session.scalar(
        db.select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == anna.id,
        )
    )
    assert mma.address == "vorstand2@club.ch"
    assert resp.get_json()["public_email"] == mma.address
