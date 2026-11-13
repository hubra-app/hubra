"""Finance blueprint: invoices, external parties and the fee basis.

The books (transactions, categories, overview, recurring bookings, the
statement and the annual accounts) are the Finances plugin
(hubra-app/hubra-plugin-finances), under the same /finance prefix."""

from __future__ import annotations


from flask import Blueprint, jsonify, request, send_file
from hubra.core.auth.helpers import get_current_member

from hubra.core.permissions import member_is_admin, permission_required, require_member
from marshmallow import ValidationError
from pydantic import ValidationError as PydanticValidationError
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


@finance_bp.get("/invoices/fee-run-preview")
@permission_required("invoices", "bulk_create", "Bulk create invoices")
def fee_run_preview():
    """What the daily invoice run would bill on ``?on=YYYY-MM-DD`` (default
    today): totals per tier, every line, who has no mail address, who was
    skipped and why. Writes nothing."""
    from datetime import date

    from hubra.api.finance.fee_run import preview

    raw = request.args.get("on")
    try:
        on = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        return api_error("VALIDATION_ERROR", "on must be a date like 2027-01-01", 400)
    return jsonify(preview(on)), 200


@finance_bp.get("/invoices/<int:id>")
@permission_required("invoices", "read", "View invoices")
def get_invoice(id: int):
    from hubra.api.finance import open_items

    invoice = InvoiceService.get(id)
    out = _invoice_schema.dump(invoice)
    out["items"] = [open_items.dump(i) for i in open_items.items_of(invoice.id)]
    return jsonify(out), 200


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


# ── Open items: one statement per member ─────────────────────────────────────


@finance_bp.get("/open-items")
@permission_required("invoices", "read", "View invoices")
def list_open_items():
    """What members owe that is not on an invoice yet, with the club's
    collecting settings (``open_items.py``)."""
    from hubra.api.finance import open_items

    conf = open_items.settings()
    member_id = request.args.get("member_id", type=int)
    return jsonify(
        {
            "items": [open_items.dump(i) for i in open_items.unbilled(member_id)],
            "cycle": conf["cycle"],
            "min_amount": float(conf["min_amount"]),
        }
    ), 200


@finance_bp.post("/open-items")
@permission_required("invoices", "create", "Create invoices")
def add_open_item():
    """An item by hand: ``{member_id, amount, text, day?, category_id?}``."""
    from hubra.api.finance import open_items
    from hubra.api.finance.contracts import OpenItemIn

    body = request.get_json(silent=True) or {}
    try:
        data = OpenItemIn.model_validate({**body, "source_ref": None, "actor_id": None})
    except PydanticValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.errors()[0]["msg"]), 400)
    actor = get_current_member().id
    item = open_items.add(
        member_id=data.member_id,
        amount=data.amount,
        text=data.text,
        source="finance",
        category_id=data.category_id,
        day=data.day,
        actor_id=actor,
    )
    db.session.commit()
    return jsonify(open_items.dump(item)), 201


@finance_bp.delete("/open-items/<int:item_id>")
@permission_required("invoices", "delete", "Delete invoices")
def delete_open_item(item_id: int):
    from hubra.api.finance import open_items
    from hubra.core.models.finance import OpenItem

    item = db.session.get(OpenItem, item_id)
    if item is None:
        return api_error("NOT_FOUND", f"Open item {item_id} not found", 404)
    open_items.remove(item)
    db.session.commit()
    return "", 204


@finance_bp.post("/open-items/bill")
@permission_required("invoices", "bulk_create", "Bulk create invoices")
def bill_open_items():
    """Bill now: one invoice per member with a positive total, without
    waiting for the first of the month and below the minimum too."""
    from hubra.api.finance import open_items

    body = request.get_json(silent=True) or {}
    member_id = body.get("member_id")
    if member_id is not None and not isinstance(member_id, int):
        return api_error("VALIDATION_ERROR", "member_id must be a number", 400)
    invoices = open_items.bill(
        member_id=member_id, force=True, actor_id=get_current_member().id
    )
    db.session.commit()
    return jsonify({"invoices": [i.id for i in invoices]}), 200


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
