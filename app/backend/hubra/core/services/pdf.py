"""One letterhead for every PDF the club sends (roadmap idea 40).

``render(body_html, title=...)`` puts *body_html* on A4 pages under the
club's letterhead: its logo, name and address at the top of every page, its
contact line and the page number at the bottom, in its primary colour.
``bottom_html`` fills the bottom of the first page instead of the footer
(the QR-bill payment slip of an invoice: 210 x 106 mm, at the page edge).

Plugins don't import this: they call the ``pdf.render`` action
(``hubra.core.contracts``), which returns the PDF as base64. Everything is
self-contained: WeasyPrint loads nothing from disk or the network, only
inline ``data:`` URIs.
"""

from __future__ import annotations

import base64
import re
from typing import Any

from pydantic import BaseModel, Field

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOGO_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml")
_MAX_LOGO_BYTES = 512 * 1024
DEFAULT_COLOR = "#181818"


def _setting(key: str) -> str:
    from hubra.core.extensions import db
    from hubra.core.models.setting import Setting

    row = db.session.get(Setting, key)
    return (row.value or "").strip() if row is not None and row.value else ""


def _tenant():
    try:
        from hubra.core.tenant.context import current_tenant

        return current_tenant()
    except Exception:  # noqa: BLE001 - outside a club: no letterhead of its own
        return None


def _logo(tenant) -> str | None:
    from hubra.core.tenant.club_settings import club_setting

    value = club_setting(tenant, "logo")
    if not isinstance(value, str):
        return None
    head, _, data = value.partition(",")
    if not head.startswith("data:") or not head.endswith(";base64"):
        return None
    if head[5:-7] not in _LOGO_TYPES or len(data) * 3 // 4 > _MAX_LOGO_BYTES:
        return None
    return value


def letterhead() -> dict[str, Any]:
    """What the letterhead shows, from Settings › Verein and the bank
    settings (Finanzen › Bank & QR-Rechnung)."""
    from hubra.core.services.email import club_display_name
    from hubra.core.tenant.club_settings import club_setting

    tenant = _tenant()
    color = club_setting(tenant, "primary_color") or ""
    street = " ".join(
        p
        for p in (_setting("Club.Banking.Street"), _setting("Club.Banking.HouseNo"))
        if p
    )
    city = " ".join(
        p
        for p in (_setting("Club.Banking.PostalCode"), _setting("Club.Banking.City"))
        if p
    )
    website = club_setting(tenant, "website") or ""
    return {
        "name": club_display_name(),
        "logo": _logo(tenant),
        "color": color
        if isinstance(color, str) and _HEX.match(color)
        else DEFAULT_COLOR,
        "address": [line for line in (street, city) if line],
        "email": _setting("Club.Contact.FinanceEmail"),
        "website": website if isinstance(website, str) else "",
    }


def html(
    body_html: str,
    *,
    title: str,
    lang: str = "de",
    bottom_html: str | None = None,
    head: dict[str, Any] | None = None,
) -> str:
    """The whole document as HTML (what ``render`` turns into a PDF)."""
    from flask import render_template

    return render_template(
        "pdf/base.html",
        body=body_html,
        title=title,
        lang="de" if (lang or "de").startswith("de") else "en",
        bottom=bottom_html,
        head=head or letterhead(),
    )


def render(
    body_html: str,
    *,
    title: str,
    lang: str = "de",
    bottom_html: str | None = None,
) -> bytes:
    """*body_html* under the club's letterhead, as PDF bytes."""
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    document = html(body_html, title=title, lang=lang, bottom_html=bottom_html)
    return HTML(
        string=document, url_fetcher=URLFetcher(allowed_protocols={"data"})
    ).write_pdf()


# ── The pdf.render action ────────────────────────────────────────────────────


class PdfIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # The plugin escapes what members wrote; WeasyPrint runs no scripts and
    # loads only data: URIs.
    body_html: str = Field(min_length=1, max_length=2_000_000)
    lang: str = "de"


class PdfOut(BaseModel):
    pdf_base64: str


def render_action(ctx, data: PdfIn) -> PdfOut:
    pdf = render(data.body_html, title=data.title, lang=data.lang)
    return PdfOut(pdf_base64=base64.b64encode(pdf).decode())
