"""Shared fixtures for mail tests."""

import pytest


@pytest.fixture(autouse=True)
def _enable_mail_feature(app):
    """Switch the mail module on for all mail tests by default.

    Uses ``app`` (not ``db``) so tests that monkeypatch ``db.session``
    (e.g. test_mail_i18n) are not affected.  Tests that explicitly test
    the disabled state switch it off after the fixture runs.
    """
    from tests.helpers import set_modules

    with app.app_context():
        set_modules(True, "members", "groups", "mail")
