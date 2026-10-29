"""DB-driven translation support for transactional email templates.

Provides ``get_mail_translator(locale)`` which returns a ``t(key, **kwargs)``
callable backed by the Translation table, and ``render_mail_template()`` which
renders the html, txt, and subject templates for a given email type.

Fallback chain:
    de-CH -> [de-CH, en-GB]
    en-GB -> [en-GB]
    other -> [de-CH, en-GB]
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import nh3
from flask import render_template
from markupsafe import Markup, escape

logger = logging.getLogger(__name__)

_FALLBACK_CHAIN: dict[str, list[str]] = {
    "de-CH": ["de-CH", "en-GB"],
    "en-GB": ["en-GB"],
}


# A club can edit its own mail texts, and some of its mail (invites) goes to
# strangers from the platform's sender: a text keeps simple formatting only,
# and a link only to the URL the mail itself fills in ({{reset_url}}, ...).
_MAIL_TAGS = {"a", "strong", "b", "em", "i", "br"}
_FOREIGN_LINK = re.compile(r'<a href="(?!\{\{\w+\}\}")[^"]*"[^>]*>')


def _safe_text(value: str) -> str:
    if "<" not in value:
        return value
    cleaned = nh3.clean(value, tags=_MAIL_TAGS, attributes={"a": {"href"}})
    return _FOREIGN_LINK.sub("<a>", cleaned)


def get_mail_translator(locale: str):
    """Return a ``t(key, **kwargs)`` function backed by the Translation table.

    Loads all translations for every locale in the fallback chain, then builds
    a single lookup dict where higher-priority locales overwrite lower ones.
    """
    from sqlalchemy import select
    from hubra.core.extensions import db
    from hubra.core.models.translation import Translation

    chain = _FALLBACK_CHAIN.get(locale, ["de-CH", "en-GB"])
    rows = db.session.scalars(
        select(Translation).where(Translation.locale.in_(chain))  # type: ignore[attr-defined]
    ).all()

    from hubra.api.i18n.services import platform_rows

    lookup: dict[str, str] = {}
    row_by_key_locale: dict[tuple[str, str], Translation] = {}
    for fallback_locale in reversed(chain):
        # A club's own texts win over the platform's, but an empty club row
        # (a key reported missing) doesn't hide the platform text.
        for prow in platform_rows(fallback_locale):
            if prow.value:
                lookup[prow.key] = prow.value
        for row in rows:
            if row.locale == fallback_locale and (row.value or row.key not in lookup):
                lookup[row.key] = row.value
                row_by_key_locale[(row.key, row.locale)] = row

    accessed_keys: set[str] = set()

    def t(key: str, **kwargs) -> Markup:
        accessed_keys.add(key)
        value = lookup.get(key)
        if value is None:
            logger.warning("mail_translation_missing key=%s locale=%s", key, locale)
            return Markup(f"[{key}]")
        value = _safe_text(value)
        if kwargs:
            for k, v in kwargs.items():
                value = value.replace("{{" + k + "}}", str(escape(v)))
        return Markup(value)

    t._accessed_keys = accessed_keys  # type: ignore[attr-defined]
    return t


def _touch_last_used(locale: str, keys: set[str]) -> None:
    """Update last_used_at for the given keys in the given locale."""
    if not keys:
        return
    from sqlalchemy import select
    from hubra.core.extensions import db
    from hubra.core.models.translation import Translation

    now = datetime.now(timezone.utc)
    rows = db.session.scalars(
        select(Translation)
        .where(Translation.locale == locale)  # type: ignore[arg-type]
        .where(Translation.key.in_(keys))  # type: ignore[attr-defined]
    ).all()
    for row in rows:
        row.last_used_at = now


def render_mail_template(
    template_name: str, locale: str, **context
) -> tuple[str, str, str]:
    """Render html, txt, and subject templates for *template_name*.

    Returns ``(html, text, subject)``.  The subject is rendered from
    ``email/<template_name>_subject.j2`` and stripped of whitespace.
    """
    t = get_mail_translator(locale)
    shared_ctx = {"t": t, "locale": locale, **context}

    html = render_template(f"email/{template_name}.html", **shared_ctx)
    # The texts carry simple HTML (<strong>, <br>) for the HTML part; the
    # plain-text part shows them as tags otherwise.
    import re
    from html import unescape

    text = render_template(f"email/{template_name}.txt", **shared_ctx)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    # t() escapes values for the HTML part; a subject is plain text.
    subject = unescape(
        render_template(f"email/{template_name}_subject.j2", **shared_ctx).strip()
    )

    _touch_last_used(locale, t._accessed_keys)  # type: ignore[attr-defined]

    return html, text, subject
