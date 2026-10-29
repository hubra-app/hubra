"""Finance service — business logic for transaction categories, transactions, and invoices."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from hubra.api.utils import escape_like, id_from_body, log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.external_party import ExternalParty
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory
from hubra.core.models.invoice_reminder import InvoiceReminderHistory
from hubra.core.models.member import Member
from hubra.core.pricing import (
    calculate_invoice_amount,
    total_deducted_annual_for_tiers,
)
from hubra.core.services.email import _get_setting
from hubra.core.services.mail_i18n import render_mail_template


# ── Shared helpers ────────────────────────────────────────────────────────────


def _delete_send_history(invoice_id: int) -> None:
    """An invoice's send history (every generated invoice has one) goes
    with the invoice; its foreign key would refuse the delete otherwise."""
    db.session.execute(
        delete(InvoiceReminderHistory).where(
            InvoiceReminderHistory.invoice_id == invoice_id
        )
    )


def _parse_page_params(args):
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(args.get("pageSize", 25))))
    except (TypeError, ValueError):
        page_size = 25
    return page, page_size


def _paginate(query, page, page_size, schema):
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    items = db.session.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "data": schema.dump(items),
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
    }


# ── TransactionCategoryService ────────────────────────────────────────────────


class TransactionCategoryService:
    """Operations on a single transaction category."""

    @staticmethod
    def get(id: int) -> TransactionCategory:
        """Return a category or raise 404."""
        category = db.session.get(TransactionCategory, id)
        if category is None:
            raise_error(404, "NOT_FOUND", f"TransactionCategory {id} not found")
        return category  # type: ignore[return-value]

    @staticmethod
    def update(category: TransactionCategory, data: dict) -> TransactionCategory:
        """Update name/color on a category."""
        if "name" in data and data["name"] != category.name:
            conflict = db.session.scalar(
                select(TransactionCategory.id)
                .where(TransactionCategory.name == data["name"])
                .where(TransactionCategory.id != category.id)
            )
            if conflict is not None:
                raise_error(
                    409, "CONFLICT", f"Category name '{data['name']}' already exists"
                )
            category.name = data["name"]
        if "color" in data:
            category.color = data["color"]
        return category

    @staticmethod
    def delete(category_id: int) -> None:
        """Delete a category if not default and no transactions reference it."""
        category = TransactionCategoryService.get(category_id)

        if category.is_default:
            raise_error(409, "CONFLICT", "Cannot delete a default category")

        has_transactions = db.session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.category_id == category.id
            )
        )
        if has_transactions:
            raise_error(
                409, "CONFLICT", "Category is referenced by existing transactions"
            )

        db.session.delete(category)


class TransactionCategoriesService:
    """Operations on the transaction category collection."""

    @staticmethod
    def list() -> list[TransactionCategory]:
        return db.session.scalars(  # type: ignore[return-value]
            select(TransactionCategory).order_by(TransactionCategory.name)
        ).all()

    @staticmethod
    def create(data: dict) -> TransactionCategory:
        """Create a new transaction category."""
        existing = db.session.scalar(
            select(TransactionCategory.id).where(
                TransactionCategory.name == data["name"]
            )
        )
        if existing is not None:
            raise_error(
                409, "CONFLICT", f"Category name '{data['name']}' already exists"
            )

        category = TransactionCategory(
            name=data["name"],
            color=data.get("color"),
        )
        db.session.add(category)
        db.session.flush()

        db.session.refresh(category)
        return category  # type: ignore[return-value]


# ── ExternalPartyService ──────────────────────────────────────────────────────


class ExternalPartyService:
    """Operations on a single external party."""

    @staticmethod
    def get(id: int) -> ExternalParty:
        """Return an external party or raise 404."""
        party = db.session.get(ExternalParty, id)
        if party is None:
            raise_error(404, "NOT_FOUND", f"ExternalParty {id} not found")
        return party  # type: ignore[return-value]

    @staticmethod
    def update(party: ExternalParty, data: dict, actor_id: int) -> ExternalParty:
        """Update allowed fields on an external party."""
        for field in (
            "name",
            "email",
            "address_street",
            "address_house_no",
            "address_postal_code",
            "address_city",
            "address_country",
            "notes",
        ):
            if field in data:
                setattr(party, field, data[field])

        log_audit(
            actor_id=actor_id,
            action="update_external_party",
            target_type="ExternalParty",
            target_id=party.id,
            target_label=party.name,
        )
        return party

    @staticmethod
    def delete(party_id: int, actor_id: int) -> None:
        """Delete an external party. Linked invoices keep their rows without
        a recipient (club schemas have no foreign keys to do this)."""
        party = ExternalPartyService.get(party_id)
        for invoice in db.session.scalars(
            select(Invoice).where(Invoice.external_party_id == party.id)
        ):
            invoice.external_party_id = None

        log_audit(
            actor_id=actor_id,
            action="delete_external_party",
            target_type="ExternalParty",
            target_id=party.id,
            target_label=party.name,
        )

        db.session.delete(party)


class ExternalPartiesService:
    """Operations on the external party collection."""

    @staticmethod
    def list(args) -> list[ExternalParty]:
        """List external parties with optional name search."""
        query = select(ExternalParty).order_by(ExternalParty.name.asc())
        search = (args.get("search") or "").strip()
        if search:
            query = query.where(
                ExternalParty.name.ilike(f"%{escape_like(search)}%", escape="\\")
            )
        return db.session.scalars(query).all()  # type: ignore[return-value]

    @staticmethod
    def create(data: dict, actor_id: int) -> ExternalParty:
        """Create a new external party."""
        party = ExternalParty(
            name=data["name"],
            email=data.get("email"),
            address_street=data.get("address_street"),
            address_house_no=data.get("address_house_no"),
            address_postal_code=data.get("address_postal_code"),
            address_city=data.get("address_city"),
            address_country=data.get("address_country", "CH"),
            notes=data.get("notes"),
        )
        db.session.add(party)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_external_party",
            target_type="ExternalParty",
            target_id=party.id,
            target_label=party.name,
        )

        db.session.refresh(party)
        return party  # type: ignore[return-value]


# ── TransactionService ────────────────────────────────────────────────────────


class TransactionService:
    """Operations on a single transaction."""

    @staticmethod
    def get(id: int) -> Transaction:
        """Return a transaction or raise 404."""
        transaction = db.session.get(Transaction, id)
        if transaction is None:
            raise_error(404, "NOT_FOUND", f"Transaction {id} not found")
        return transaction  # type: ignore[return-value]

    @staticmethod
    def update(transaction: Transaction, data: dict, actor_id: int) -> Transaction:
        """Update allowed fields on a transaction."""
        if "category_id" in data:
            category = db.session.get(TransactionCategory, data["category_id"])
            if category is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"Transaction category {data['category_id']} not found",
                )

        if "member_id" in data and data["member_id"] is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == data["member_id"])
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"Member {data['member_id']} not found or archived",
                )

        for field in (
            "status",
            "description",
            "date",
            "amount",
            "method",
            "type",
            "category_id",
            "member_id",
            "payee_name",
        ):
            if field in data:
                setattr(transaction, field, data[field])

        # The API takes amounts as positive numbers and stores expenses
        # negative (as create does); keep that when amount or type change.
        if "amount" in data or "type" in data:
            amount = abs(Decimal(str(transaction.amount)))
            transaction.amount = -amount if transaction.type == "expense" else amount

        # Booking an invoice's income as received pays the invoice, so no
        # reminder goes to someone who paid (and the other way round).
        if "status" in data:
            invoice = db.session.scalar(
                select(Invoice).where(Invoice.transaction_id == transaction.id)
            )
            if invoice is not None:
                if transaction.status == "Completed" and invoice.status != "Paid":
                    InvoiceService.update(invoice, {"status": "Paid"}, actor_id)
                elif transaction.status == "Pending" and invoice.status == "Paid":
                    InvoiceService.update(invoice, {"status": "Open"}, actor_id)

        log_audit(
            actor_id=actor_id,
            action="update_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=transaction.description,
        )
        return transaction

    @staticmethod
    def delete(transaction_id: int, actor_id: int) -> None:
        """Delete a transaction, unlinking cascade invoice if present."""
        transaction = TransactionService.get(transaction_id)

        log_audit(
            actor_id=actor_id,
            action="delete_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=transaction.description,
        )

        linked_invoice = db.session.scalar(
            select(Invoice).where(Invoice.transaction_id == transaction.id)
        )
        if linked_invoice is not None:
            linked_invoice.transaction_id = None
            _delete_send_history(linked_invoice.id)
            db.session.flush()
            db.session.delete(linked_invoice)
            db.session.flush()

        db.session.delete(transaction)


class TransactionsService:
    """Operations on the transaction collection."""

    @staticmethod
    def list(args, schema) -> dict:
        """List transactions with filtering and pagination."""
        page, page_size = _parse_page_params(args)

        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.category),
                selectinload(Transaction.member).selectinload(Member.user),
                selectinload(Transaction.invoice),
            )
            .order_by(Transaction.date.desc(), Transaction.id.desc())
        )

        search = args.get("search", "").strip()
        if search:
            query = query.where(
                Transaction.description.ilike(f"%{escape_like(search)}%", escape="\\")
            )

        tx_type = args.get("type", "").strip()
        if tx_type:
            query = query.where(Transaction.type == tx_type)

        category_name = args.get("category", "").strip()
        if category_name:
            query = query.join(
                TransactionCategory,
                Transaction.category_id == TransactionCategory.id,
            ).where(TransactionCategory.name == category_name)

        from_date = args.get("from", "").strip()
        if from_date:
            try:
                query = query.where(Transaction.date >= date.fromisoformat(from_date))
            except ValueError:
                pass

        to_date = args.get("to", "").strip()
        if to_date:
            try:
                query = query.where(Transaction.date <= date.fromisoformat(to_date))
            except ValueError:
                pass

        return _paginate(query, page, page_size, schema)  # schema injected by route

    @staticmethod
    def create(data: dict, actor_id: int) -> Transaction:
        """Create a new transaction."""
        member_id = data.get("member_id")
        if member_id is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == member_id)
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404, "NOT_FOUND", f"Member {member_id} not found or archived"
                )

        category_id = data.get("category_id")
        category = db.session.get(TransactionCategory, category_id)
        if not category:
            raise_error(
                404, "NOT_FOUND", f"Transaction category {category_id} not found"
            )

        amount = data["amount"]
        if data["type"] == "expense":
            amount = -abs(amount)

        transaction = Transaction(
            date=data["date"],
            description=data["description"],
            category_id=category_id,
            member_id=member_id,
            payee_name=data.get("payee_name"),
            amount=amount,
            method=data["method"],
            type=data["type"],
        )
        db.session.add(transaction)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_transaction",
            target_type="Transaction",
            target_id=transaction.id,
            target_label=data["description"],
        )

        db.session.refresh(transaction)
        return transaction  # type: ignore[return-value]


# ── InvoiceService ────────────────────────────────────────────────────────────


class InvoiceService:
    """Operations on a single invoice."""

    @staticmethod
    def get(id: int) -> Invoice:
        """Return an invoice or raise 404."""
        invoice = db.session.get(Invoice, id)
        if invoice is None:
            raise_error(404, "NOT_FOUND", f"Invoice {id} not found")
        return invoice  # type: ignore[return-value]

    @staticmethod
    def update(invoice: Invoice, data: dict, actor_id: int) -> Invoice:
        """Update allowed fields on an invoice."""
        if "member_id" in data and data["member_id"] is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == data["member_id"])
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"Member {data['member_id']} not found or archived",
                )

        if "external_party_id" in data and data["external_party_id"] is not None:
            ext = db.session.get(ExternalParty, data["external_party_id"])
            if ext is None:
                raise_error(
                    404,
                    "NOT_FOUND",
                    f"ExternalParty {data['external_party_id']} not found",
                )

        was_paid = invoice.status == "Paid"
        for field in (
            "member_id",
            "external_party_id",
            "issued",
            "due",
            "amount",
            "status",
            "purpose",
            "description",
        ):
            if field in data:
                setattr(invoice, field, data[field])

        linked_tx = (
            db.session.get(Transaction, invoice.transaction_id)
            if invoice.transaction_id is not None
            else None
        )
        if linked_tx is not None:
            # The linked income follows the invoice: paid → completed, and
            # back to pending when a payment is taken back. Its amount
            # follows while the money is still expected.
            if invoice.status == "Paid":
                linked_tx.status = "Completed"
            elif was_paid:
                linked_tx.status = "Pending"
            if "amount" in data and linked_tx.status == "Pending":
                linked_tx.amount = abs(Decimal(str(invoice.amount)))
            # So does who pays: the income is listed under the new recipient.
            if "member_id" in data or "external_party_id" in data:
                linked_tx.member_id = invoice.member_id
                party = (
                    db.session.get(ExternalParty, invoice.external_party_id)
                    if invoice.external_party_id is not None
                    else None
                )
                linked_tx.payee_name = party.name if party else None

        if invoice.status == "Paid" and not was_paid and invoice.member_id:
            from hubra.core.modules import emit
            from hubra.core.modules.events import INVOICE_PAID

            emit(INVOICE_PAID, member_id=invoice.member_id, invoice_id=invoice.id)

        log_audit(
            actor_id=actor_id,
            action="update_invoice",
            target_type="Invoice",
            target_id=invoice.id,
            target_label=f"Invoice {invoice.id}",
        )
        return invoice

    @staticmethod
    def delete(invoice_id: int, actor_id: int) -> None:
        """Delete an invoice and its linked transaction."""
        invoice = InvoiceService.get(invoice_id)

        log_audit(
            actor_id=actor_id,
            action="delete_invoice",
            target_type="Invoice",
            target_id=invoice.id,
            target_label=f"Invoice {invoice.id}",
        )

        linked_tx_id = invoice.transaction_id
        invoice.transaction_id = None
        _delete_send_history(invoice.id)
        db.session.flush()
        db.session.delete(invoice)
        db.session.flush()

        if linked_tx_id is not None:
            linked_tx = db.session.get(Transaction, linked_tx_id)
            if linked_tx is not None:
                db.session.delete(linked_tx)

    @staticmethod
    def remind(invoice: Invoice, actor_id: int) -> None:
        """Log reminder audit."""
        log_audit(
            actor_id=actor_id,
            action="invoice_reminder",
            target_type="Invoice",
            target_id=invoice.id,
            target_label=f"Invoice {invoice.id}",
        )

    @staticmethod
    def download_pdf(invoice: Invoice) -> bytes:
        """Generate a QR-bill PDF for the invoice and return the bytes."""
        from hubra.core.services.qr_bill import (
            QRBillNotConfigured,
            generate_invoice_pdf,
        )

        try:
            return generate_invoice_pdf(invoice)
        except QRBillNotConfigured as exc:
            # Banking details (IBAN, postal code, city) not set up yet.
            raise_error(409, "QR_BILL_NOT_CONFIGURED", str(exc))
        except ValueError as exc:
            # The invoice itself cannot be paid by QR bill (e.g. a credit
            # note with a negative amount).
            raise_error(422, "QR_BILL_INVALID", str(exc))

    @staticmethod
    def dispatch_reminder(invoice: Invoice, actor_id: int) -> dict:
        """Dispatch reminder email via Celery. Call after commit.

        Branches on recipient type:
        - Member with verified email → reminder with portal link (current behavior).
        - External party with email → reminder without portal link.
        """
        import logging

        from hubra.core.tasks.email_tasks import send_email_task

        member = (
            db.session.get(Member, invoice.member_id) if invoice.member_id else None
        )
        ext = (
            db.session.get(ExternalParty, invoice.external_party_id)
            if invoice.external_party_id
            else None
        )
        _logger = logging.getLogger(__name__)
        success = False
        error_message = None

        recipient_email = ""
        recipient_name = ""

        if member and member.email and member.private_email_verified:
            from hubra.core.services.email import _get_base_url

            _base = _get_base_url()
            club_name = _get_setting("club.name", "Your Club")
            portal_url = f"{_base}/invoices" if _base else ""

            lang = getattr(member, "language", "de-CH") or "de-CH"
            body_html, body_text, subject = render_mail_template(
                "invoice_reminder",
                locale=lang,
                name=member.name,
                club_name=club_name,
                invoice_id=invoice.id,
                amount_formatted=f"CHF {invoice.amount:.2f}",
                due_date=invoice.due.isoformat(),
                portal_url=portal_url,
            )
            send_email_task.delay(
                to_email=member.email,
                to_name=member.name,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            _logger.info(
                "invoice_reminder_queued invoice_id=%s member_id=%s",
                invoice.id,
                member.id,
            )
            recipient_email = member.email
            recipient_name = member.name
            success = True
        elif member and not member.email:
            error_message = "no email address"
            recipient_email = member.email or ""
            recipient_name = member.name
        elif member and not member.private_email_verified:
            error_message = "email not verified"
            recipient_email = member.email or ""
            recipient_name = member.name
        elif ext and ext.email:
            club_name = _get_setting("club.name", "Your Club")
            lang = "de-CH"
            body_html, body_text, subject = render_mail_template(
                "invoice_reminder",
                locale=lang,
                name=ext.name,
                club_name=club_name,
                invoice_id=invoice.id,
                amount_formatted=f"CHF {invoice.amount:.2f}",
                due_date=invoice.due.isoformat(),
                portal_url="",
            )
            send_email_task.delay(
                to_email=ext.email,
                to_name=ext.name,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            _logger.info(
                "invoice_reminder_queued invoice_id=%s external_party_id=%s",
                invoice.id,
                ext.id,
            )
            recipient_email = ext.email
            recipient_name = ext.name
            success = True
        elif ext and not ext.email:
            error_message = "no email address"
            recipient_name = ext.name
        else:
            error_message = "no recipient email"

        # Record in InvoiceReminderHistory
        db.session.add(
            InvoiceReminderHistory(
                invoice_id=invoice.id,
                reminder_type="manual",
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                success=success,
                error_message=error_message,
            )
        )

        reminded_at = datetime.now(timezone.utc).isoformat()
        if not success:
            return {"ok": False, "message": error_message, "remindedAt": None}
        return {"ok": True, "message": "Reminder queued", "remindedAt": reminded_at}


def _link_pending_transaction(
    invoice: Invoice,
    member_id: int | None,
    *,
    external_party: ExternalParty | None = None,
    category: TransactionCategory | None = None,
    category_id: int | None = None,
) -> None:
    """Create a Pending income transaction and link it to the invoice.

    Category resolution order:
      1. *category* (explicit ORM object, used by bulk_create).
      2. *category_id* (from the create form, e.g. purpose='other').
      3. "Membership" category (default for purpose='membership').
      4. First available category (fallback).
      5. None → skip the linked transaction entirely.

    For external recipients: member_id=None, payee_name=external_party.name.
    """
    if category is None and category_id is not None:
        category = db.session.get(TransactionCategory, category_id)
    if category is None:
        category = db.session.scalar(
            select(TransactionCategory).where(TransactionCategory.name == "Membership")
        )
        if category is None:
            category = db.session.scalar(select(TransactionCategory))
    if category is None:
        return

    payee_name = external_party.name if external_party else None

    linked_tx = Transaction(
        date=invoice.issued,
        description=f"Invoice #{invoice.id}",
        category_id=category.id,
        member_id=member_id,
        payee_name=payee_name,
        amount=invoice.amount,
        method="IBAN",
        type="income",
        status="Pending",
    )
    db.session.add(linked_tx)
    db.session.flush()
    invoice.transaction_id = linked_tx.id
    db.session.flush()


class InvoicesService:
    """Operations on the invoice collection."""

    @staticmethod
    def list(args, schema) -> dict:
        """List invoices with filtering and pagination."""
        page, page_size = _parse_page_params(args)
        today = date.today()

        query = (
            select(Invoice)
            .options(
                selectinload(Invoice.member).selectinload(Member.user),
                selectinload(Invoice.external_party),
            )
            .order_by(Invoice.due.desc(), Invoice.id.desc())
        )

        status_filter = args.get("status", "").strip()
        if status_filter == "Overdue":
            query = query.where(Invoice.due < today).where(Invoice.status != "Paid")
        elif status_filter:
            query = query.where(Invoice.status == status_filter)

        purpose_filter = (args.get("purpose") or "").strip()
        if purpose_filter:
            query = query.where(Invoice.purpose == purpose_filter)

        recipient_search = (args.get("member") or "").strip()
        if recipient_search:
            like = f"%{escape_like(recipient_search)}%"
            # Match either member name or external party name.
            query = (
                query.outerjoin(Member, Invoice.member_id == Member.id)
                .outerjoin(ExternalParty, Invoice.external_party_id == ExternalParty.id)
                .where(
                    (Member.name.ilike(like, escape="\\"))  # type: ignore[attr-defined]
                    | (ExternalParty.name.ilike(like, escape="\\"))
                )
            )

        return _paginate(query, page, page_size, schema)

    @staticmethod
    def create(data: dict, actor_id: int) -> Invoice:
        """Create an invoice with auto-linked transaction.

        Recipient is either a member (member_id) or an external party
        (external_party_id); the schema enforces exactly one.
        """
        member_id = data.get("member_id")
        external_party_id = data.get("external_party_id")
        purpose = data.get("purpose", "membership")
        category_id = data.get("category_id")

        member = None
        external_party = None

        if member_id is not None:
            member = db.session.scalar(
                select(Member)
                .where(Member.id == member_id)
                .where(Member.archived_at.is_(None))
            )
            if member is None:
                raise_error(
                    404, "NOT_FOUND", f"Member {member_id} not found or archived"
                )

        if external_party_id is not None:
            external_party = db.session.get(ExternalParty, external_party_id)
            if external_party is None:
                raise_error(
                    404, "NOT_FOUND", f"ExternalParty {external_party_id} not found"
                )

        invoice = Invoice(
            member_id=member_id,
            external_party_id=external_party_id,
            issued=data["issued"],
            due=data["due"],
            amount=data["amount"],
            status=data.get("status", "Open"),
            purpose=purpose,
            description=data.get("description"),
        )
        db.session.add(invoice)
        db.session.flush()

        _link_pending_transaction(
            invoice,
            member_id,
            external_party=external_party,
            category_id=category_id,
        )

        recipient_label = (
            member.name if member else (external_party.name if external_party else "?")
        )
        log_audit(
            actor_id=actor_id,
            action="create_invoice",
            target_type="Invoice",
            target_id=invoice.id,
            target_label=f"Invoice for {recipient_label}",
        )

        db.session.refresh(invoice)
        return invoice  # type: ignore[return-value]

    @staticmethod
    def bulk_create(body: dict, actor_id: int) -> dict:
        """Create one invoice per active member, optionally filtered by tier."""
        due_str = body.get("due")
        tier_id = id_from_body(body.get("tier_id"), "tier_id")
        description = body.get("description") or None
        if description is not None and not isinstance(description, str):
            raise_error(400, "VALIDATION_ERROR", "description must be text")

        if not due_str:
            raise_error(400, "VALIDATION_ERROR", "due date is required")
        try:
            due_date = date.fromisoformat(due_str)
        except (TypeError, ValueError):
            raise_error(400, "VALIDATION_ERROR", "due must be a valid ISO date")

        issued_date = date.today()

        member_q = (
            select(Member)
            .options(selectinload(Member.tier))
            .where(Member.archived_at.is_(None))
        )
        if tier_id is not None:
            member_q = member_q.where(Member.tier_id == tier_id)

        members = db.session.scalars(member_q).all()
        if not members:
            raise_error(
                404, "NOT_FOUND", "No active members found for the given filter"
            )

        membership_cat = db.session.scalar(
            select(TransactionCategory).where(TransactionCategory.name == "Membership")
        )
        if membership_cat is None:
            membership_cat = db.session.scalar(select(TransactionCategory))

        formula_deduct_ids: set[int] = set()
        for member in members:
            t = member.tier
            if t and t.price_type == "formula" and t.deduct_tier_ids:
                formula_deduct_ids.update(t.deduct_tier_ids)
        total_deducted = total_deducted_annual_for_tiers(db.session, formula_deduct_ids)

        created = []
        for member in members:
            tier = member.tier
            if not tier:
                continue
            amount = float(calculate_invoice_amount(member, tier, total_deducted))
            if amount <= 0:
                continue

            invoice = Invoice(
                member_id=member.id,
                issued=issued_date,
                due=due_date,
                amount=amount,
                status="Open",
                purpose="membership",
                description=description,
            )
            db.session.add(invoice)
            db.session.flush()

            _link_pending_transaction(invoice, member.id, category=membership_cat)

            log_audit(
                actor_id=actor_id,
                action="create_invoice",
                target_type="Invoice",
                target_id=invoice.id,
                target_label=f"Bulk invoice for member {member.id}",
            )
            created.append(invoice)

        for inv in created:
            db.session.refresh(inv)
        return created  # type: ignore[return-value]

    @staticmethod
    def list_mine(member_id: int, args, schema) -> dict:
        """Return paginated invoices for a specific member."""
        page, page_size = _parse_page_params(args)
        query = (
            select(Invoice)
            .where(Invoice.member_id == member_id)
            .order_by(Invoice.due.desc(), Invoice.id.desc())
        )
        return _paginate(query, page, page_size, schema)


# ── FinanceOverviewService ────────────────────────────────────────────────────


class FinanceOverviewService:
    """Aggregated finance overview."""

    @staticmethod
    def get() -> dict:
        """Return balance, MTD figures, 12-month history, and open invoice stats."""
        today = date.today()
        current_year = today.year
        current_month = today.month

        balance = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.status == "Completed"
                )
            )
            or 0
        )

        mtd_income = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.status == "Completed")
                .where(func.extract("year", Transaction.date) == current_year)
                .where(func.extract("month", Transaction.date) == current_month)
                .where(Transaction.amount > 0)
            )
            or 0
        )

        mtd_expense_raw = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.status == "Completed")
                .where(func.extract("year", Transaction.date) == current_year)
                .where(func.extract("month", Transaction.date) == current_month)
                .where(Transaction.amount < 0)
            )
            or 0
        )

        income_mtd = float(mtd_income)
        expenses_mtd = abs(float(mtd_expense_raw))
        net_mtd = income_mtd - expenses_mtd

        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        months_data = []
        for i in range(11, -1, -1):
            month_offset = (current_month - 1 - i) % 12 + 1
            year_offset = current_year + ((current_month - 1 - i) // 12)

            inc = (
                db.session.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .where(Transaction.status == "Completed")
                    .where(func.extract("year", Transaction.date) == year_offset)
                    .where(func.extract("month", Transaction.date) == month_offset)
                    .where(Transaction.amount > 0)
                )
                or 0
            )

            exp = (
                db.session.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .where(Transaction.status == "Completed")
                    .where(func.extract("year", Transaction.date) == year_offset)
                    .where(func.extract("month", Transaction.date) == month_offset)
                    .where(Transaction.amount < 0)
                )
                or 0
            )

            months_data.append(
                {
                    "m": month_names[month_offset - 1],
                    "year": int(year_offset),
                    "month": int(month_offset),
                    "inc": round(float(inc) / 1000, 2),
                    "exp": round(abs(float(exp)) / 1000, 2),
                }
            )

        open_stats = db.session.execute(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.amount), 0),
            ).where(Invoice.status != "Paid")
        ).one()
        open_count = open_stats[0] or 0
        open_amount = open_stats[1] or 0

        return {
            "balance": float(balance),
            "incomeMTD": income_mtd,
            "expensesMTD": expenses_mtd,
            "netMTD": net_mtd,
            "months": months_data,
            "openInvoices": {
                "count": open_count,
                "amount": float(open_amount),
            },
        }


# ── InvoiceReminderHistoryService ─────────────────────────────────────────────


class InvoiceReminderHistoryService:
    """Operations on invoice reminder history."""

    @staticmethod
    def list_by_invoice(invoice_id: int) -> list[dict]:
        """Return all reminder history entries for a given invoice, newest first."""
        entries = (
            db.session.execute(
                select(InvoiceReminderHistory)
                .where(InvoiceReminderHistory.invoice_id == invoice_id)
                .order_by(InvoiceReminderHistory.sent_at.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": e.id,
                "invoiceId": e.invoice_id,
                "sentAt": e.sent_at.isoformat(),
                "reminderType": e.reminder_type,
                "recipientEmail": e.recipient_email,
                "recipientName": e.recipient_name,
                "success": e.success,
                "errorMessage": e.error_message,
            }
            for e in entries
        ]
