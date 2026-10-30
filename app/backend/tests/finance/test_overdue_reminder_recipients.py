"""Automatic overdue reminders follow the manual reminder's rule: external
parties get them, members only at a verified address."""

from datetime import date, timedelta
from decimal import Decimal

from hubra.core.models.finance import Invoice
from tests.finance.test_overdue_reminders import _types, run  # noqa: F401


def _overdue(db, **who):
    invoice = Invoice(
        issued=date.today() - timedelta(days=40),
        due=date.today() - timedelta(days=8),
        amount=Decimal("80.00"),
        status="Open",
        **who,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


def test_an_external_party_is_reminded_without_a_portal_link(
    db, seeded_db, run  # noqa: F811
):
    from hubra.core.models.external_party import ExternalParty

    party = ExternalParty(name="Sponsor AG", email="kasse@sponsor.ch")
    db.session.add(party)
    db.session.commit()
    invoice = _overdue(db, external_party_id=party.id)

    result, mail, emit = run()

    assert result["overdue_7d"] == 1
    kwargs = mail.call_args.kwargs
    assert kwargs["to_email"] == "kasse@sponsor.ch"
    assert "/invoices" not in kwargs["body_text"]
    assert _types(db, invoice) == {"overdue_7d"}
    emit.assert_not_called()  # invoice.overdue names a member


def test_a_member_without_a_verified_address_is_skipped(
    db, seeded_db, run  # noqa: F811
):
    admin = seeded_db["admin"]
    admin.private_email_verified = False
    db.session.commit()
    invoice = _overdue(db, member_id=admin.id)

    result, mail, _ = run()

    assert result["overdue_7d"] == 0
    assert result["skipped_no_email"] == 1
    mail.assert_not_called()
    # Nothing recorded, so the reminder goes out once the address is verified.
    assert _types(db, invoice) == set()
