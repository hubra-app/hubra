"""Settings > Verein > Bank & QR-Rechnung: the account QR invoices are paid to."""

from unittest.mock import patch

import pytest

from hubra.api.settings.services import SettingService
from hubra.core.models.tenant import Tenant

QR_IBAN = "CH4431999123000889012"  # SIX example QR-IBAN (IID 31999)
IBAN = "CH9300762011623852957"


@pytest.fixture
def tenant_ctx(db, seeded_db):
    tenant = Tenant(name="Test Club", slug="test-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    with (
        patch("hubra.api.admin.routes.current_tenant", return_value=tenant),
        patch("hubra.core.tenant.context.set_search_path"),
    ):
        yield tenant


@pytest.fixture
def admin(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    return client


ADDRESS = {
    "street": "Seestrasse",
    "houseNo": "12",
    "postalCode": "8000",
    "city": "Zürich",
    "country": "ch",
}


def test_saving_a_qr_iban_is_what_invoices_read(tenant_ctx, admin):
    resp = admin.put(
        "/api/v1/admin/bank-settings",
        json={"iban": "CH44 3199 9123 0008 8901 2", **ADDRESS},
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["iban"] == QR_IBAN
    assert body["country"] == "CH"
    assert body["isQrIban"] is True
    assert body["complete"] is True
    # The QR-bill PDF reads these keys.
    assert SettingService.get("Club.Banking.Iban") == QR_IBAN
    assert SettingService.get("Club.Banking.PostalCode") == "8000"
    assert SettingService.get("Club.Banking.City") == "Zürich"

    assert admin.get("/api/v1/admin/bank-settings").get_json() == body


def test_a_normal_iban_is_accepted_but_has_no_qr_reference(tenant_ctx, admin):
    body = admin.put(
        "/api/v1/admin/bank-settings", json={"iban": IBAN, **ADDRESS}
    ).get_json()
    assert body["isQrIban"] is False
    assert body["complete"] is True


@pytest.mark.parametrize(
    "iban", ["CH4431999123000889013", "DE89370400440532013000", "CH12"]
)
def test_a_wrong_iban_is_refused(tenant_ctx, admin, iban):
    resp = admin.put("/api/v1/admin/bank-settings", json={"iban": iban, **ADDRESS})
    assert resp.status_code == 400
    assert SettingService.get("Club.Banking.Iban", "") in ("", None)


def test_incomplete_without_postal_code_and_city(tenant_ctx, admin):
    body = admin.put("/api/v1/admin/bank-settings", json={"iban": IBAN}).get_json()
    assert body["complete"] is False


def test_needs_sign_in(client, db):
    assert client.get("/api/v1/admin/bank-settings").status_code == 401
