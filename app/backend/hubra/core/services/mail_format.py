"""How dates look in mails, by the reader's language."""

from __future__ import annotations

from datetime import date


def mail_date(value: date, locale: str | None) -> str:
    """A due date as people in that language write it: 15.11.2026 for
    German, French and Italian, 15/11/2026 for English."""
    if (locale or "").lower().startswith("en"):
        return value.strftime("%d/%m/%Y")
    return value.strftime("%d.%m.%Y")
