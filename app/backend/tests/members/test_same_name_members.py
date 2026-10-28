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
