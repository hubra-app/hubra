"""Finance blueprint: invoices, external parties and the fee basis.

The books (transactions, categories, overview, recurring bookings, the
statement and the annual accounts) are the Finances plugin
(hubra-app/hubra-plugin-finances), under the same /finance prefix."""

from __future__ import annotations


from flask import Blueprint, jsonify, request, send_file
from hubra.core.auth.helpers import get_current_member

from hubra.core.permissions import member_is_admin, permission_required, require_member
from marshmallow import ValidationError
from hubra.core.errors import api_error, validation_error
from hubra.core.extensions import db
from hubra.core.schemas.finance import (
    InvoiceCreateSchema,
    InvoiceSchema,
    InvoiceUpdateSchema,
    ExternalPartyCreateSchema,
    ExternalPartySchema,
    ExternalPartyUpdateSchema,
)
from hubra.api.finance.services import (
    InvoiceService,
    InvoicesService,
    InvoiceReminderHistoryService,
    ExternalPartyService,
    ExternalPartiesService,
)


finance_bp = Blueprint("finance_bp", __name__)

_invoice_schema = InvoiceSchema()
_invoices_schema = InvoiceSchema(many=True)
_invoice_create_schema = InvoiceCreateSchema()
_invoice_update_schema = InvoiceUpdateSchema()

_ext_party_schema = ExternalPartySchema()
_ext_parties_schema = ExternalPartySchema(many=True)
_ext_party_create_schema = ExternalPartyCreateSchema()
_ext_party_update_schema = ExternalPartyUpdateSchema()


@finance_bp.get("/external-parties")
@permission_required("external_parties", "read", "View external parties")
def list_external_parties():
    parties = ExternalPartiesService.list(request.args)
    return jsonify(_ext_parties_schema.dump(parties)), 200


@finance_bp.post("/external-parties")
@permission_required("external_parties", "create", "Create external parties")
def create_external_party():
    body = request.get_json(silent=True) or {}
    try:
        data = _ext_party_create_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)

    party = ExternalPartiesService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_ext_party_schema.dump(party)), 201


@finance_bp.patch("/external-parties/<int:id>")
@permission_required("external_parties", "update", "Update external parties")
def update_external_party(id: int):
    party = ExternalPartyService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _ext_party_update_schema.load(body, partial=True)
    except ValidationError as exc:
        return validation_error(exc)

    ExternalPartyService.update(party, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(party)
    return jsonify(_ext_party_schema.dump(party)), 200


@finance_bp.delete("/external-parties/<int:id>")
@permission_required("external_parties", "delete", "Delete external parties")
def delete_external_party(id: int):
    ExternalPartyService.delete(id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── Invoices ──────────────────────────────────────────────────────────────────


@finance_bp.get("/invoices")
@permission_required("invoices", "read", "View invoices")
def list_invoices():
    return jsonify(InvoicesService.list(request.args, _invoices_schema)), 200


@finance_bp.get("/invoices/<int:id>")
@permission_required("invoices", "read", "View invoices")
def get_invoice(id: int):
    invoice = InvoiceService.get(id)
    return jsonify(_invoice_schema.dump(invoice)), 200


@finance_bp.post("/invoices")
@permission_required("invoices", "create", "Create invoices")
def create_invoice():
    body = request.get_json(silent=True) or {}
    try:
        data = _invoice_create_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)

    invoice = InvoicesService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_invoice_schema.dump(invoice)), 201


@finance_bp.patch("/invoices/<int:id>")
@permission_required("invoices", "update", "Update invoices")
def update_invoice(id: int):
    invoice = InvoiceService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _invoice_update_schema.load(body)
    except ValidationError as exc:
        return validation_error(exc)

    InvoiceService.update(invoice, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(invoice)
    return jsonify(_invoice_schema.dump(invoice)), 200


@finance_bp.delete("/invoices/<int:id>")
@permission_required("invoices", "delete", "Delete invoices")
def delete_invoice(id: int):
    InvoiceService.delete(id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


@finance_bp.post("/invoices/bulk")
@permission_required("invoices", "bulk_create", "Bulk create invoices")
def bulk_create_invoices():
    body = request.get_json(silent=True) or {}
    created = InvoicesService.bulk_create(body, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(
        {"created": len(created), "invoices": _invoices_schema.dump(created)}
    ), 201


@finance_bp.post("/invoices/<int:id>/remind")
@permission_required("invoices", "remind", "Send invoice reminders")
def remind_invoice(id: int):
    member = get_current_member()
    invoice = InvoiceService.get(id)
    result = InvoiceService.remind(invoice, member.id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    result = InvoiceService.dispatch_reminder(invoice, member.id)
    db.session.commit()  # keeps the failed attempt in the reminder history
    if not result["ok"]:
        return api_error(
            "REMINDER_NOT_SENT", f"Reminder not sent: {result['message']}", 409
        )
    return jsonify(result), 200


@finance_bp.get("/invoices/<int:id>/reminders")
@permission_required("invoices", "read_reminders", "View invoice reminders")
def list_invoice_reminders(id: int):
    InvoiceService.get(id)  # ensure invoice exists
    history = InvoiceReminderHistoryService.list_by_invoice(id)
    return jsonify(history), 200


@finance_bp.get("/invoices/mine")
@require_member
def list_my_invoices():
    member_id = get_current_member().id
    return jsonify(
        InvoicesService.list_mine(member_id, request.args, _invoices_schema)
    ), 200


def _reads_invoices(member) -> bool:
    """A role with invoices:read (a treasurer) sees every member's invoice."""
    from hubra.core.permissions import _get_member_permission_keys

    return "finance.invoices.read" in _get_member_permission_keys(member)


@finance_bp.get("/invoices/<int:id>/qr-bill.pdf")
@require_member
def download_invoice_pdf(id: int):
    """Download a QR-bill invoice PDF for the given invoice.

    Access rules:
      - Member invoices: the owning member, an admin or a role with
        invoices:read.
      - External-party invoices: admin only (no member owner).
    """
    invoice = InvoiceService.get(id)
    # 403 for a sign-in that is not a member of this club.
    member = get_current_member()

    is_admin = member_is_admin(member)

    if invoice.member_id is not None:
        is_owner = invoice.member_id == member.id
        if not is_owner and not (is_admin or _reads_invoices(member)):
            from hubra.core.errors import raise_error as _raise

            _raise(403, "FORBIDDEN", "You do not have access to this invoice")
    else:
        # External-party invoice — admin only.
        if not is_admin:
            from hubra.core.errors import raise_error as _raise

            _raise(403, "FORBIDDEN", "Only admins can download external-party invoices")

    pdf_bytes = InvoiceService.download_pdf(invoice)

    from io import BytesIO

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"invoice-{invoice.id}.pdf",
    )


@finance_bp.get("/fee-basis")
@permission_required("overview", "read", "View finance overview")
def get_fee_basis():
    """How the yearly expenses behind percentage and formula tiers come
    together; ?source=&extra=&manual= previews a choice before saving."""
    from decimal import Decimal

    from hubra.api.finance.fee_basis import fee_basis, tier_effects

    overrides = {
        key: request.args[arg]
        for arg, key in (
            ("source", "fee_basis_source"),
            ("extra", "fee_basis_extra"),
            ("manual", "fee_basis_manual"),
        )
        if arg in request.args
    }
    basis = fee_basis(overrides)
    basis["tiers"] = tier_effects(Decimal(str(basis["total"])))
    return jsonify(basis), 200
