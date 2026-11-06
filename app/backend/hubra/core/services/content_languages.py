"""Content in several languages: the languages a post can be written in
and the checks for its translations.

The club app's own texts are translated by the platform (translations are
platform-only); this is the club's own content. A post has its language
(``posts.language``) and translations in other languages
(``posts.translations``), written by hand or pre-filled by machine
translation (``services.machine_translation``).
"""

from __future__ import annotations

from marshmallow import ValidationError

# Switzerland's languages and English.
CONTENT_LANGUAGES = ("de", "fr", "it", "en")
FIELDS = {"title": 255, "summary": 500, "body": None}


def clean_translations(
    value, language: str | None, body_max: int
) -> dict[str, dict[str, str | None]] | None:
    """Validated translations, or None for none.  Raises ValidationError."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError("translations must be an object by language")
    out: dict[str, dict[str, str | None]] = {}
    for lang, entry in value.items():
        if lang not in CONTENT_LANGUAGES:
            raise ValidationError(f"Unknown language: {lang}")
        if lang == language:
            raise ValidationError(f"{lang} is the post's own language")
        if not isinstance(entry, dict) or set(entry) - set(FIELDS):
            raise ValidationError(f"{lang}: title, summary and body only")
        title = (entry.get("title") or "").strip()
        body = entry.get("body") or ""
        summary = entry.get("summary")
        if not title and not body.strip():
            continue  # an empty language is no translation
        if not title or not body.strip():
            raise ValidationError(f"{lang}: needs a title and a text")
        if not isinstance(title, str) or len(title) > FIELDS["title"]:
            raise ValidationError(f"{lang}: title up to 255 characters")
        if not isinstance(body, str) or len(body) > body_max:
            raise ValidationError(f"{lang}: text too long")
        if summary is not None and (not isinstance(summary, str) or len(summary) > 500):
            raise ValidationError(f"{lang}: summary up to 500 characters")
        out[lang] = {"title": title, "summary": summary or None, "body": body}
    return out or None
