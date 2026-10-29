"""The mail server is shared by every club: a club only reaches its own addresses."""

from unittest.mock import MagicMock, patch

from tests.helpers import patch_mail_domain

FOREIGN_ID = "a" * 24
OWN_ID = "c" * 24


def _wd():
    wd = MagicMock()
    wd.list_addresses.return_value = {
        "results": [
            {"id": FOREIGN_ID, "address": "info@other-club.ch", "targets": ["p@x.ch"]},
            {"id": OWN_ID, "address": "info@club.ch", "targets": ["q@x.ch"]},
        ]
    }
    wd.get_address.side_effect = lambda wd_id: {
        "id": wd_id,
        "address": "info@club.ch" if wd_id == OWN_ID else "info@other-club.ch",
    }
    wd.get_user.side_effect = lambda wd_id: {
        "id": wd_id,
        "address": "box@club.ch" if wd_id == OWN_ID else "box@other-club.ch",
    }
    wd.find_forwarding_alias_by_address.return_value = None
    wd.create_forwarding_alias.return_value = {"id": "b" * 24}
    return wd


def test_alias_list_leaves_out_other_clubs(client, auth_headers):
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=_wd()),
        patch_mail_domain("club.ch"),
    ):
        r = client.get("/api/v1/mail/aliases", headers=auth_headers)
    assert r.status_code == 200
    assert [a["address"] for a in r.get_json()["data"]] == ["info@club.ch"]


def test_other_clubs_alias_cannot_be_changed_or_deleted(client, auth_headers):
    wd = _wd()
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=wd),
        patch_mail_domain("club.ch"),
    ):
        r1 = client.patch(
            f"/api/v1/mail/aliases/{FOREIGN_ID}",
            json={"deliversTo": ["x@example.org"]},
            headers=auth_headers,
        )
        r2 = client.delete(f"/api/v1/mail/aliases/{FOREIGN_ID}", headers=auth_headers)
    assert (r1.status_code, r2.status_code) == (404, 404)
    wd.update_forwarding_alias.assert_not_called()
    wd.delete_forwarding_alias.assert_not_called()


def test_other_clubs_mailbox_cannot_be_changed_or_deleted(client, auth_headers):
    wd = _wd()
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=wd),
        patch_mail_domain("club.ch"),
    ):
        r1 = client.patch(
            f"/api/v1/mail/mailboxes/{FOREIGN_ID}",
            json={"displayName": "x"},
            headers=auth_headers,
        )
        r2 = client.delete(f"/api/v1/mail/mailboxes/{FOREIGN_ID}", headers=auth_headers)
    assert (r1.status_code, r2.status_code) == (404, 404)
    wd.update_user.assert_not_called()
    wd.delete_user.assert_not_called()


def test_alias_and_system_address_only_in_the_club_domain(client, auth_headers):
    wd = _wd()
    with (
        patch("hubra.api.mail.services.try_get_client", return_value=wd),
        patch("hubra.core.services.wildduck.try_get_client", return_value=wd),
        patch_mail_domain("club.ch"),
    ):
        r1 = client.post(
            "/api/v1/mail/aliases",
            json={"address": "info@other-club.ch", "deliversTo": ["x@example.org"]},
            headers=auth_headers,
        )
        r2 = client.post(
            "/api/v1/mail/system-addresses",
            json={
                "address": "info@other-club.ch",
                "addressType": "alias",
                "forwardTargets": ["x@example.org"],
            },
            headers=auth_headers,
        )
    assert r1.status_code == 400
    assert r2.status_code == 400
    wd.create_forwarding_alias.assert_not_called()


def test_a_domain_another_club_verified_is_not_ours(app, db):
    from hubra.core.models.domain import Domain
    from hubra.core.models.tenant import Tenant
    from hubra.core.services.managed_mail import owns_mail_address

    other = Tenant(name="Other", slug="other-club")
    db.session.add(other)
    db.session.flush()
    db.session.add(Domain(tenant_id=other.id, domain="club.ch", verified=True))
    db.session.flush()
    with patch_mail_domain("club.ch"):
        assert owns_mail_address("info@club.ch") is False
    with patch_mail_domain("own.ch"):
        assert owns_mail_address("info@own.ch") is True
        assert owns_mail_address("info@own.ch.evil.org") is False
