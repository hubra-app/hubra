"""QR-bill invoice PDF generation.

Generates a full A4 itemized invoice with a Swiss QR-bill payment part
at the bottom, positioned per SIX specification (5mm margin, bottom 105mm).

Creditor details are read from the settings/club/* namespace.
Debtor details are read from the Member's structured address fields.
"""

from __future__ import annotations

import logging
from io import StringIO


from hubra.core.models.finance import Invoice

logger = logging.getLogger(__name__)

# What the QR bill itself holds (SIX spec); the invoice above it shows all.
_MAX_INFO = 140
_MAX_NAME = 70


class QRBillNotConfigured(ValueError):
    """The club's banking details are missing or refused by the QR bill."""


def _fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"

# ── Setting helpers (same pattern as email.py) ─────────────────────────────

_DEFAULT_LANG = "de-CH"


def _get_setting(key: str, default: str = "") -> str:
    """Read a single value from the Setting KV store."""
    try:
        from hubra.api.settings.services import SettingService

        return SettingService.get(key, default=default) or default
    except Exception as exc:
        logger.warning("Could not load setting %r: %s", key, exc)
        return default


def _get_member_lang(member) -> str:
    return getattr(member, "language", _DEFAULT_LANG) or _DEFAULT_LANG


# ── Public API ─────────────────────────────────────────────────────────────


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """Generate a full A4 invoice PDF with QR-bill payment part at bottom.

    Args:
        invoice: The Invoice record (with .member and .external_party
            relationships loaded).

    Returns:
        PDF bytes of the generated invoice document.

    Raises:
        ValueError: If the invoice has no recipient (neither member nor
            external party) or required banking settings are missing.
    """
    member = invoice.member
    ext = invoice.external_party
    lang = _get_member_lang(member) if member else _DEFAULT_LANG

    if member is None and ext is None:
        raise ValueError(f"Invoice {invoice.id} has no recipient")

    # ── 1. Gather creditor info from settings ──────────────────────────────
    from hubra.core.services.email import club_display_name

    club_name = club_display_name()
    iban = _get_setting("Club.Banking.Iban", "")
    creditor_street = _get_setting("Club.Banking.Street", "")
    creditor_house_no = _get_setting("Club.Banking.HouseNo", "")
    creditor_pcode = _get_setting("Club.Banking.PostalCode", "")
    creditor_city = _get_setting("Club.Banking.City", "")
    creditor_country = _get_setting("Club.Banking.Country", "CH")
    finance_email = _get_setting("Club.Contact.FinanceEmail", "")

    if not iban:
        raise QRBillNotConfigured(
            "Club.Banking.Iban is not configured — cannot generate QR-bill"
        )
    if not creditor_pcode or not creditor_city:
        raise QRBillNotConfigured(
            "Club.Banking.PostalCode and Club.Banking.City must be configured "
            "— cannot generate QR-bill"
        )

    # ── 2. Build description ───────────────────────────────────────────────
    description = invoice.description or _description_for(invoice, lang=lang)

    # ── 3. Determine reference type from IBAN ──────────────────────────────
    # QR-IBAN (IID 30/31) allows QRR references; regular IBAN gets no reference
    clean_iban = iban.replace(" ", "").upper()
    iid = clean_iban[4:6]
    is_qr_iban = iid in ("30", "31")

    reference = None
    if is_qr_iban:
        from hubra.core.services.qr_reference import generate_qrr_reference

        # member_id=0 is the sentinel for external-party invoices.
        reference = generate_qrr_reference(
            member_id=member.id if member else 0,
            invoice_id=invoice.id,
            year=invoice.issued.year,
        )

    # ── 4. Build debtor address ────────────────────────────────────────────
    if member is not None:
        recipient_name = member.name
        debtor_street = member.address_street or ""
        debtor_house_no = member.address_house_no or ""
        debtor_pcode = member.address_postal_code or ""
        debtor_city = member.address_city or ""
        debtor_country = member.address_country or "CH"
    else:
        recipient_name = ext.name  # type: ignore[union-attr]
        debtor_street = ext.address_street or ""  # type: ignore[union-attr]
        debtor_house_no = ext.address_house_no or ""  # type: ignore[union-attr]
        debtor_pcode = ext.address_postal_code or ""  # type: ignore[union-attr]
        debtor_city = ext.address_city or ""  # type: ignore[union-attr]
        debtor_country = ext.address_country or "CH"  # type: ignore[union-attr]

    has_full_debtor = all([debtor_street, debtor_house_no, debtor_pcode, debtor_city])

    # ── 5. Generate QR-bill SVG ────────────────────────────────────────────
    _ensure_dependencies()

    from qrbill import QRBill

    creditor_address = {
        "name": _fit(club_name, _MAX_NAME),
        "street": creditor_street,
        "house_num": creditor_house_no,
        "pcode": creditor_pcode,
        "city": creditor_city,
        "country": creditor_country,
    }

    debtor_address = None
    if has_full_debtor:
        debtor_address = {
            "name": _fit(recipient_name, _MAX_NAME),
            "street": debtor_street,
            "house_num": debtor_house_no,
            "pcode": debtor_pcode,
            "city": debtor_city,
            "country": debtor_country,
        }

    def _bill(debtor: dict | None) -> QRBill:
        return QRBill(
            account=iban,
            creditor=creditor_address,
            debtor=debtor,
            amount=str(invoice.amount),
            currency="CHF",
            reference_number=reference,
            additional_information=_fit(description, _MAX_INFO),
            language="de" if lang and lang.startswith("de") else "en",
            top_line=True,
            payment_line=True,
        )

    try:
        bill = _bill(debtor_address)
    except ValueError as exc:
        message = str(exc)
        if "IBAN" in message or "creditor" in message:
            raise QRBillNotConfigured(message) from exc
        if debtor_address is None or "debtor" not in message:
            raise
        # An address the QR bill refuses (a street over 70 characters,
        # "UK" instead of GB): the payer fills it in instead.
        bill = _bill(None)

    # Render QR-bill SVG (full A4 page with bill at bottom)
    svg_buffer = StringIO()
    bill.as_svg(svg_buffer, full_page=True)
    qr_svg = svg_buffer.getvalue()

    # ── 6. Render full invoice HTML ────────────────────────────────────────
    from flask import render_template

    html = render_template(
        "invoice/invoice.html",
        club_name=club_name,
        iban=iban,
        creditor_street=creditor_street,
        creditor_house_no=creditor_house_no,
        creditor_pcode=creditor_pcode,
        creditor_city=creditor_city,
        creditor_country=creditor_country,
        finance_email=finance_email,
        recipient_name=recipient_name,
        invoice_id=invoice.id,
        issued=invoice.issued.isoformat(),
        due=invoice.due.isoformat(),
        amount_float=float(invoice.amount),
        description=description,
        reference=reference,
        qr_svg=qr_svg,
        lang=lang,
    )

    # ── 7. Convert HTML to PDF via WeasyPrint ──────────────────────────────
    try:
        from weasyprint import HTML as WeasyHTML

        pdf_bytes = WeasyHTML(string=html, url_fetcher=_no_fetch()).write_pdf()
    except Exception as exc:
        logger.error("WeasyPrint PDF generation failed: %s", exc)
        raise RuntimeError(f"Failed to generate invoice PDF: {exc}") from exc

    return pdf_bytes


def _no_fetch():
    """WeasyPrint's url_fetcher: the invoice is self-contained, so nothing is
    loaded from disk or the network (only inline data: URIs)."""
    from weasyprint.urls import URLFetcher

    return URLFetcher(allowed_protocols={"data"})


def _description_for(invoice: Invoice, lang: str = _DEFAULT_LANG) -> str:
    """Return a human-readable description for the invoice."""
    if lang and lang.startswith("de"):
        return f"Mitgliederbeitrag {invoice.issued.year}"
    return f"Membership fee {invoice.issued.year}"


def _ensure_dependencies() -> None:
    """Check that optional dependencies are importable (imported lazily)."""
    missing = []
    try:
        import qrbill  # noqa: F401
    except ImportError:
        missing.append("qrbill")
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        missing.append("weasyprint")
    if missing:
        raise RuntimeError(
            f"Missing required dependencies: {', '.join(missing)}. "
            f"Install with: pip install {' '.join(missing)}"
        )
