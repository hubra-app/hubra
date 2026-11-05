"""Finance blueprint — TransactionCategories, Transactions, Invoices, Overview."""

from __future__ import annotations


from flask import Blueprint, jsonify, request, send_file
from hubra.core.auth.helpers import get_current_member

from hubra.core.permissions import member_is_admin, permission_required, require_member
from marshmallow import ValidationError
from hubra.core.errors import api_error, raise_error
from hubra.core.models.finance import TransactionCategory
from hubra.core.utils import log_audit
from hubra.core.extensions import db
from hubra.core.schemas.finance import (
    InvoiceCreateSchema,
    InvoiceSchema,
    InvoiceUpdateSchema,
    TransactionCategoryCreateSchema,
    TransactionCategorySchema,
    TransactionCreateSchema,
    TransactionSchema,
    TransactionUpdateSchema,
    ExternalPartyCreateSchema,
    ExternalPartySchema,
    ExternalPartyUpdateSchema,
)
from hubra.api.finance.services import (
    TransactionCategoryService,
    TransactionCategoriesService,
    TransactionService,
    TransactionsService,
    InvoiceService,
    InvoicesService,
    InvoiceReminderHistoryService,
    FinanceOverviewService,
    FinanceSummaryService,
    ExternalPartyService,
    ExternalPartiesService,
)

from hubra.api.finance.recurring import (
    RecurringTransactionService,
    recurring_to_dict,
)

finance_bp = Blueprint("finance_bp", __name__)

_category_schema = TransactionCategorySchema()
_categories_schema = TransactionCategorySchema(many=True)
_category_create_schema = TransactionCategoryCreateSchema()

_transaction_schema = TransactionSchema()
_transactions_schema = TransactionSchema(many=True)
_transaction_create_schema = TransactionCreateSchema()
_transaction_update_schema = TransactionUpdateSchema()

_invoice_schema = InvoiceSchema()
_invoices_schema = InvoiceSchema(many=True)
_invoice_create_schema = InvoiceCreateSchema()
_invoice_update_schema = InvoiceUpdateSchema()

_ext_party_schema = ExternalPartySchema()
_ext_parties_schema = ExternalPartySchema(many=True)
_ext_party_create_schema = ExternalPartyCreateSchema()
_ext_party_update_schema = ExternalPartyUpdateSchema()


# ── Transaction Categories ────────────────────────────────────────────────────


@finance_bp.get("/transaction-categories")
@permission_required("transaction_categories", "read", "View transaction categories")
def list_transaction_categories():
    return jsonify(_categories_schema.dump(TransactionCategoriesService.list())), 200


@finance_bp.post("/transaction-categories")
@permission_required(
    "transaction_categories", "create", "Create transaction categories"
)
def create_transaction_category():
    body = request.get_json(silent=True) or {}
    try:
        data = _category_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    category = TransactionCategoriesService.create(data)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_category_schema.dump(category)), 201


@finance_bp.patch("/transaction-categories/<int:id>")
@permission_required(
    "transaction_categories", "update", "Update transaction categories"
)
def update_transaction_category(id: int):
    category = TransactionCategoryService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _category_create_schema.load(body, partial=True)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    TransactionCategoryService.update(category, data)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(category)
    return jsonify(_category_schema.dump(category)), 200


@finance_bp.delete("/transaction-categories/<int:id>")
@permission_required(
    "transaction_categories", "delete", "Delete transaction categories"
)
def delete_transaction_category(id: int):
    TransactionCategoryService.delete(id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── Transactions ──────────────────────────────────────────────────────────────


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
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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


# ── Transactions ──────────────────────────────────────────────────────────────


@finance_bp.get("/transactions")
@permission_required("transactions", "read", "View transactions")
def list_transactions():
    return jsonify(TransactionsService.list(request.args, _transactions_schema)), 200


@finance_bp.get("/transactions/<int:id>")
@permission_required("transactions", "read", "View transactions")
def get_transaction(id: int):
    return jsonify(_transaction_schema.dump(TransactionService.get(id))), 200


@finance_bp.post("/transactions")
@permission_required("transactions", "create", "Create transactions")
def create_transaction():
    body = request.get_json(silent=True) or {}
    try:
        data = _transaction_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    transaction = TransactionsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_transaction_schema.dump(transaction)), 201


@finance_bp.patch("/transactions/<int:id>")
@permission_required("transactions", "update", "Update transactions")
def update_transaction(id: int):
    transaction = TransactionService.get(id)

    body = request.get_json(silent=True) or {}
    try:
        data = _transaction_update_schema.load(body, partial=True)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    TransactionService.update(transaction, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(transaction)
    return jsonify(_transaction_schema.dump(transaction)), 200


@finance_bp.delete("/transactions/<int:id>")
@permission_required("transactions", "delete", "Delete transactions")
def delete_transaction(id: int):
    TransactionService.delete(id, get_current_member().id)

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
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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


# ── Finance Overview ──────────────────────────────────────────────────────────


@finance_bp.get("/overview")
@permission_required("overview", "read", "View finance overview")
def finance_overview():
    return jsonify(FinanceOverviewService.get()), 200


@finance_bp.get("/summary")
@permission_required("overview", "read", "View finance overview")
def finance_summary():
    return jsonify(FinanceSummaryService.get(request.args)), 200


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


# ── Recurring transactions ────────────────────────────────────────────────────


@finance_bp.get("/recurring")
@permission_required("transactions", "read", "View transactions")
def list_recurring():
    rules = RecurringTransactionService.list()
    return jsonify([recurring_to_dict(r) for r in rules]), 200


@finance_bp.post("/recurring")
@permission_required("transactions", "create", "Create transactions")
def create_recurring():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected a JSON object", 400)
    rule = RecurringTransactionService.create(body, get_current_member().id)
    db.session.commit()
    return jsonify(recurring_to_dict(rule)), 201


@finance_bp.patch("/recurring/<int:id>")
@permission_required("transactions", "update", "Update transactions")
def update_recurring(id: int):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error("VALIDATION_ERROR", "Expected a JSON object", 400)
    rule = RecurringTransactionService.update(id, body, get_current_member().id)
    db.session.commit()
    return jsonify(recurring_to_dict(rule)), 200


@finance_bp.delete("/recurring/<int:id>")
@permission_required("transactions", "delete", "Delete transactions")
def delete_recurring(id: int):
    RecurringTransactionService.delete(id, get_current_member().id)
    db.session.commit()
    return "", 204


# ── Monthly account statement ─────────────────────────────────────────────────


@finance_bp.get("/statement.pdf")
@permission_required("overview", "read", "View finance overview")
def download_statement():
    """The account statement of ?month=YYYY-MM (last month by default)."""
    from io import BytesIO

    from hubra.api.finance.statement import month_of, statement_data, statement_pdf

    start = month_of(request.args.get("month"))
    pdf = statement_pdf(statement_data(start))
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"kontoauszug-{start:%Y-%m}.pdf",
    )


@finance_bp.post("/statement/send")
@permission_required("overview", "read", "View finance overview")
def send_statement_now():
    """Mail a month's statement to the club's statement address now."""
    from hubra.api.finance.statement import month_of, send_statement, statement_settings

    body = request.get_json(silent=True) or {}
    email = statement_settings()["email"]
    if "@" not in email:
        return api_error(
            "STATEMENT_EMAIL_MISSING",
            "Set the address for the account statement first",
            400,
        )
    month = body.get("month") if isinstance(body, dict) else None
    result = send_statement(month_of(month if isinstance(month, str) else None), email)
    db.session.commit()
    return jsonify(result), 202


# ── Annual accounts (Jahresrechnung) ──────────────────────────────────────────


def _year_arg(year: int) -> int:
    if not 1900 <= year <= 2999:
        raise_error(400, "VALIDATION_ERROR", "Unknown year")
    return year


@finance_bp.get("/accounts")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def list_accounts():
    """The chart of accounts and which account each category counts on."""
    from hubra.api.finance import annual

    data = annual.list_chart()
    db.session.commit()  # the chart is seeded on first read
    return jsonify(data)


@finance_bp.post("/accounts")
@permission_required("accounts", "update", "Change the chart of accounts")
def create_account():
    from hubra.api.finance import annual

    account = annual.create_account(request.get_json(silent=True) or {})
    log_audit(
        get_current_member().id,
        "create_account",
        "Account",
        account.id,
        f"{account.number} {account.name}",
    )
    db.session.commit()
    return jsonify(annual.account_dict(account)), 201


@finance_bp.patch("/accounts/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def update_account(id: int):
    from hubra.api.finance import annual
    from hubra.core.models.finance import Account

    account = db.session.get(Account, id) or raise_error(
        404, "NOT_FOUND", "Account not found"
    )
    annual.update_account(account, request.get_json(silent=True) or {})
    db.session.commit()
    return jsonify(annual.account_dict(account))


@finance_bp.delete("/accounts/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def delete_account(id: int):
    from hubra.api.finance import annual
    from hubra.core.models.finance import Account

    account = db.session.get(Account, id) or raise_error(
        404, "NOT_FOUND", "Account not found"
    )
    label = f"{account.number} {account.name}"
    annual.delete_account(account)
    log_audit(get_current_member().id, "delete_account", "Account", id, label)
    db.session.commit()
    return "", 204


@finance_bp.put("/accounts/categories/<int:id>")
@permission_required("accounts", "update", "Change the chart of accounts")
def map_category_account(id: int):
    """``{"accountId": int | null}``: the account a category counts on."""
    from hubra.api.finance import annual

    category = db.session.get(TransactionCategory, id) or raise_error(
        404, "NOT_FOUND", "Category not found"
    )
    body = request.get_json(silent=True) or {}
    account_id = body.get("accountId")
    if account_id is not None and (
        not isinstance(account_id, int) or isinstance(account_id, bool)
    ):
        raise_error(400, "VALIDATION_ERROR", "accountId must be a number or null")
    annual.map_category(category, account_id)
    db.session.commit()
    return jsonify({"id": category.id, "accountId": category.account_id})


@finance_bp.get("/annual")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def list_fiscal_years():
    from hubra.api.finance import annual

    years = annual.years_overview()
    db.session.commit()
    return jsonify({"years": years, "startMonth": annual.start_month()})


@finance_bp.get("/annual/<int:year>")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def get_annual_accounts(year: int):
    from hubra.api.finance import annual

    report = annual.annual_report(_year_arg(year))
    db.session.commit()
    return jsonify(report)


@finance_bp.get("/annual/<int:year>.pdf")
@permission_required(
    "accounts", "read", "View the chart of accounts and annual accounts"
)
def download_annual_accounts(year: int):
    from io import BytesIO

    from hubra.api.finance import annual

    lang = (
        "en" if (request.args.get("lang") or "").lower().startswith("en") else "de-CH"
    )
    report = annual.annual_report(_year_arg(year))
    pdf = annual.annual_pdf(report, lang)
    db.session.commit()
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"jahresrechnung-{year}.pdf",
    )


@finance_bp.put("/annual/<int:year>/opening")
@permission_required("accounts", "update", "Change the chart of accounts")
def set_opening_balances(year: int):
    """``{"balances": {account number: amount}}`` for an open year whose year
    before is not closed (the first year in Hubra)."""
    from hubra.api.finance import annual

    body = request.get_json(silent=True) or {}
    balances = body.get("balances")
    if not isinstance(balances, dict):
        raise_error(400, "VALIDATION_ERROR", "balances must be an object")
    annual.set_opening(_year_arg(year), balances)
    log_audit(
        get_current_member().id, "set_opening_balances", "FiscalYear", year, str(year)
    )
    db.session.commit()
    return jsonify(annual.annual_report(year))


@finance_bp.post("/annual/<int:year>/close")
@permission_required("accounts", "close", "Close and reopen a fiscal year")
def close_fiscal_year(year: int):
    """Store the closing balances; bookings in the year are refused after."""
    from hubra.api.finance import annual

    member = get_current_member()
    annual.close_year(_year_arg(year), member.id)
    log_audit(member.id, "close_fiscal_year", "FiscalYear", year, str(year))
    db.session.commit()
    return jsonify(annual.annual_report(year))


@finance_bp.post("/annual/<int:year>/reopen")
@permission_required("accounts", "close", "Close and reopen a fiscal year")
def reopen_fiscal_year(year: int):
    from hubra.api.finance import annual

    annual.reopen_year(_year_arg(year))
    log_audit(
        get_current_member().id, "reopen_fiscal_year", "FiscalYear", year, str(year)
    )
    db.session.commit()
    return jsonify(annual.annual_report(year))
