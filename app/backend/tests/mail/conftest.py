"""Shared fixtures for mail tests."""

import pytest


@pytest.fixture(autouse=True)
def _enable_mail_feature(app):
    """Enable the 'mail' FeatureFlag for all mail tests by default.

    Uses ``app`` (not ``db``) so tests that monkeypatch ``db.session``
    (e.g. test_mail_i18n) are not affected.  Tests that explicitly test
    the disabled state override this by setting the flag to False after
    the fixture runs.
    """
    from vollbuild.core.extensions import db
    from vollbuild.core.models.feature_flag import FeatureFlag

    with app.app_context():
        flag = db.session.get(FeatureFlag, "mail")
        if flag is None:
            db.session.add(FeatureFlag(key="mail", enabled=True, label="Mail"))
            db.session.commit()
        elif not flag.enabled:
            flag.enabled = True
            db.session.commit()
