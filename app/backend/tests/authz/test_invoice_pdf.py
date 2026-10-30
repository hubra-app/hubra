"""Invoice PDFs with a QR bill: who may download them, and what comes out.

Treasurers downloading members' invoices is fixed and tested in PR #42.
"""

from datetime import date

import pytest

from hubra.core.tenant.service import DEFAULT_ROLE_PERMISSIONS

QR_IBAN = "CH44 3199 9123 0008 8901 2"
IBAN = "CH93 0076 2011 6238 5295 7"


@pytest.fixture
def banking(db):
    from hubra.core.models.setting import Setting

    def _set(iban):
        values = {
            "Club.Banking.Iban": iban,
            "Club.Banking.Street": "Seestrasse",
            "Club.Banking.HouseNo": "1",
            "Club.Banking.PostalCode": "8000",
            "Club.Banking.City": "Zürich",
        }
        for key, value in values.items():
            db.session.merge(Setting(key=key, value=value, namespace="finance"))
        db.session.commit()

    return _set


def _invoice(db, member_id=None, description=None, external=False):
    from hubra.core.models.external_party import ExternalParty
    from hubra.core.models.finance import Invoice

    party_id = None
    if external:
        party = ExternalParty(name="Gemeinde")
        db.session.add(party)
        db.session.flush()
        party_id = party.id
    invoice = Invoice(
        member_id=member_id,
        external_party_id=party_id,
        issued=date(2026, 1, 1),
        due=date(2026, 2, 1),
        amount=45,
        status="Open",
        description=description,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice.id


def _pdf(client, invoice_id, headers):
    return client.get(f"/api/v1/finance/invoices/{invoice_id}/qr-bill.pdf", headers=headers)


def test_plain_member_gets_only_their_own(
    client, db, seeded_db, banking, permissioned_member_factory
):
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    banking(QR_IBAN)
    headers = permissioned_member_factory(
        DEFAULT_ROLE_PERMISSIONS["Member"], email="plain-pdf@test.ch"
    )
    me = (
        db.session.query(Member.id)
        .join(User, User.id == Member.user_id)
        .filter(User.email == "plain-pdf@test.ch")
        .scalar()
    )
    assert _pdf(client, _invoice(db, member_id=me), headers).status_code == 200
    other = _invoice(db, member_id=seeded_db["admin"].id)
    assert _pdf(client, other, headers).status_code == 403
    assert _pdf(client, _invoice(db, external=True), headers).status_code == 403


def test_awkward_invoices_still_get_a_qr_bill(client, db, seeded_db, banking, auth_headers):
    """A description over 140 characters or a member address the QR bill
    refuses (a street over 70 characters, "UK" for GB) made the PDF fail, so the
    member could not download it and the invoice mail went without it."""
    from hubra.core.models.member import Member

    banking(QR_IBAN)
    admin = db.session.get(Member, seeded_db["admin"].id)
    user = admin.user
    user.address_street, user.address_house_no = "Hauptstrasse " * 6, "5"
    user.address_postal_code, user.address_city = "8001", "Zürich"
    user.address_country = "UK"
    db.session.commit()

    invoice_id = _invoice(db, member_id=admin.id, description="Beitrag " * 30)
    resp = _pdf(client, invoice_id, auth_headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.data.startswith(b"%PDF")


def test_a_bad_iban_is_a_setup_problem_and_a_credit_note_is_refused(
    client, db, seeded_db, banking, auth_headers
):
    from hubra.core.models.finance import Invoice

    banking("CH00 1234")
    invoice_id = _invoice(db, member_id=seeded_db["admin"].id)
    resp = _pdf(client, invoice_id, auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "QR_BILL_NOT_CONFIGURED"

    banking(IBAN)
    db.session.get(Invoice, invoice_id).amount = -20
    db.session.commit()
    resp = _pdf(client, invoice_id, auth_headers)
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "QR_BILL_INVALID"


def test_the_payment_slip_is_printed_at_full_size(
    client, db, seeded_db, banking, auth_headers, monkeypatch
):
    """SIX: the payment part is 210 x 105 mm at the bottom of an A4 page and
    must not be scaled. The full-page SVG went into a 200 x 105 mm box, so the
    slip came out at a third of its size and the QR code was 16 mm wide."""
    import flask

    from hubra.core.models.member import Member

    seen = {}
    render = flask.render_template

    def spy(name, **context):
        seen.update(context)
        return render(name, **context)

    monkeypatch.setattr(flask, "render_template", spy)
    banking(QR_IBAN)
    admin = db.session.get(Member, seeded_db["admin"].id)
    resp = _pdf(client, _invoice(db, member_id=admin.id), auth_headers)
    assert resp.status_code == 200, resp.get_json()

    svg = seen["qr_svg"]
    assert 'width="210mm"' in svg and 'height="106mm"' in svg
    assert seen["reference_display"].count(" ") == 5  # 2 + 5 x 5 digits
