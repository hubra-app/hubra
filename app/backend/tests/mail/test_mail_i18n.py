"""Tests for the mail i18n translation function and template rendering."""

import json
import re
from pathlib import Path

from markupsafe import Markup

from hubra.core.services.mail_i18n import get_mail_translator, render_mail_template


class _FakeRow:
    """Minimal stand-in for a Translation ORM row."""

    def __init__(self, key: str, value: str, locale: str):
        self.key = key
        self.value = value
        self.locale = locale
        self.last_used_at = None


def _patch_translations(monkeypatch, rows):
    """Patch db.session.scalars to return *rows* for Translation queries."""
    from hubra.core.extensions import db

    class _FakeScalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _FakeSession:
        def scalars(self, stmt):
            return _FakeScalars(rows)

    monkeypatch.setattr(db, "session", _FakeSession())


def test_t_returns_markup_with_html_tags(monkeypatch):
    """t() should return Markup so HTML tags in translation values are not escaped."""
    rows = [_FakeRow("mail.test.bold", "Hello <b>World</b>", "en-GB")]
    _patch_translations(monkeypatch, rows)

    t = get_mail_translator("en-GB")
    result = t("mail.test.bold")

    assert isinstance(result, Markup)
    assert "<b>World</b>" in str(result)


def test_t_escapes_kwarg_values(monkeypatch):
    """t() should escape kwarg values to prevent XSS."""
    rows = [_FakeRow("mail.test.greeting", "Hi {{name}}", "en-GB")]
    _patch_translations(monkeypatch, rows)

    t = get_mail_translator("en-GB")
    result = t("mail.test.greeting", name="<script>alert(1)</script>")

    assert "<script>" not in str(result)
    assert "&lt;script&gt;" in str(result)


def test_t_returns_markup_for_missing_key(monkeypatch):
    """Missing keys should return Markup placeholder."""
    _patch_translations(monkeypatch, [])

    t = get_mail_translator("en-GB")
    result = t("mail.nonexistent.key")

    assert isinstance(result, Markup)
    assert "[mail.nonexistent.key]" == str(result)


def test_t_falls_back_to_en_gb(monkeypatch):
    """When locale is de-CH and only en-GB translation exists, fallback should work."""
    rows = [_FakeRow("mail.test.fallback", "Welcome", "en-GB")]
    _patch_translations(monkeypatch, rows)

    t = get_mail_translator("de-CH")
    result = t("mail.test.fallback")

    assert "Welcome" in str(result)


def test_render_mail_template_html_not_escaped(app, monkeypatch):
    """render_mail_template should produce HTML with unescaped translation tags."""
    rows = [
        _FakeRow("mail.email.greeting", "Hello {{name}}", "en-GB"),
        _FakeRow(
            "mail.email.footer", "Sent by <strong>{{club_name}}</strong>", "en-GB"
        ),
        _FakeRow(
            "mail.email.welcome.intro", "Welcome to <b>{{club_name}}</b>!", "en-GB"
        ),
        _FakeRow("mail.email.welcome.login_email", "Login email", "en-GB"),
        _FakeRow("mail.email.welcome.login_password", "Password", "en-GB"),
        _FakeRow(
            "mail.email.welcome.cta",
            'Click <a href="{{login_url}}">here</a> to login.',
            "en-GB",
        ),
        _FakeRow("mail.email.welcome.closing", "Goodbye", "en-GB"),
        _FakeRow("mail.email.subject.welcome", "Welcome", "en-GB"),
    ]
    _patch_translations(monkeypatch, rows)

    html, text, subject = render_mail_template(
        "welcome",
        "en-GB",
        name="Alice",
        club_name="ACME",
        login_email="alice@example.com",
        temp_password="secret",
        login_url="https://example.com/login",
    )

    # Translation HTML tags should be unescaped
    assert "<b>" in html
    assert "<strong>" in html
    assert '<a href="https://example.com/login"' in html
    # No escaped versions of translation tags
    assert "&lt;b&gt;" not in html
    assert "&lt;strong&gt;" not in html


# ── Template-seed key consistency ─────────────────────────────────────────────

_T_KEY_RE = re.compile(r"""t\(\s*['"]([^'"]+)['"]""")


def _extract_template_keys() -> set[str]:
    """Scan all email templates for t('key') calls and return the set of keys."""
    template_dir = (
        Path(__file__).resolve().parent.parent.parent / "hubra" / "templates" / "email"
    )
    keys: set[str] = set()
    for pattern in ("*.html", "*.txt", "*.j2"):
        for path in template_dir.glob(pattern):
            text = path.read_text(encoding="utf-8")
            keys.update(_T_KEY_RE.findall(text))
    return keys


def _load_seed_keys(locale: str) -> set[str]:
    """Load translation keys from a seed JSON file."""
    seed_path = (
        Path(__file__).resolve().parent.parent.parent
        / "hubra"
        / "core"
        / "seed_data"
        / "translations"
        / f"{locale}.json"
    )
    with open(seed_path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.keys())


def test_all_email_template_keys_exist_in_seeds():
    """Every t('key') call in email templates must have a matching seed entry.

    This guards against key-naming drift between templates and seed JSON files.
    See: https://gitlab.com/VollBuild/club-operations-suite/-/merge_requests/23
    """
    template_keys = _extract_template_keys()
    assert template_keys, "No t() keys found in email templates — check _T_KEY_RE"

    seed_keys = _load_seed_keys("en-GB") | _load_seed_keys("de-CH")

    missing = template_keys - seed_keys
    assert not missing, (
        f"Email template keys with no seed JSON entry (neither en-GB nor de-CH): "
        f"{sorted(missing)}"
    )
