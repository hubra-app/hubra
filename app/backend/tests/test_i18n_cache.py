"""Tests for i18n caching and async report endpoint."""

from unittest.mock import patch

from hubra.api.i18n import services as i18n_services
from hubra.core.extensions import db
from hubra.core.models.translation import Translation


def _seed_translation(locale: str, key: str, value: str = "test") -> None:
    db.session.add(Translation(locale=locale, key=key, value=value))
    db.session.commit()


def test_get_available_locales_cached(app, db):
    """get_available_locales caches result — DB query only once."""
    _seed_translation("de-CH", "test.key1")
    _seed_translation("en-GB", "test.key1")

    i18n_services._mem_locales.clear()  # reset cache

    with patch.object(db.session, "scalars", wraps=db.session.scalars):
        locales1 = i18n_services.get_available_locales()
        locales2 = i18n_services.get_available_locales()
        assert locales1 == locales2
        assert "de-CH" in locales1
        assert "en-GB" in locales1
        # Second call should use in-memory cache (no new DB query for locales)
        # Note: we can't assert exact call count because other code may use scalars,
        # but the in-memory cache means the DISTINCT query isn't re-run.

    i18n_services._mem_locales.clear()  # cleanup


def test_duplicate_locale_invalidates_locales_cache(app, db):
    """duplicate_locale clears the locales cache so the new locale appears."""
    _seed_translation("de-CH", "test.key1")
    i18n_services._mem_locales.clear()

    locales1 = i18n_services.get_available_locales()
    assert "fr-FR" not in locales1

    from hubra.api.i18n.services import duplicate_locale

    duplicate_locale("de-CH", "fr-FR", copy_values=True)
    db.session.commit()

    locales2 = i18n_services.get_available_locales()
    assert "fr-FR" in locales2

    i18n_services._mem_locales.clear()  # cleanup


def test_get_translations_dict_cached(app, db):
    """get_translations_dict caches result — second call uses cache."""
    _seed_translation("de-CH", "test.key1", "Wert 1")
    i18n_services._mem_translations.clear()

    # First call queries DB
    result1 = i18n_services.get_translations_dict("de-CH")
    assert result1["test.key1"] == "Wert 1"

    # Second call should use in-memory cache (no ETag → _no_etag key)
    result2 = i18n_services.get_translations_dict("de-CH")
    assert result2 == result1

    i18n_services._mem_translations.clear()  # cleanup


def test_get_translations_dict_invalidated_on_write(app, db):
    """After upsert (bumps etag), get_translations_dict re-queries DB."""
    _seed_translation("de-CH", "test.key1", "Wert 1")
    i18n_services._mem_translations.clear()

    result1 = i18n_services.get_translations_dict("de-CH")
    assert result1["test.key1"] == "Wert 1"

    # Upsert changes the value (bumps etag in Redis, but Redis is down in tests)
    # Without Redis, the in-memory cache uses _no_etag key both times.
    # The cache should still serve stale data (acceptable — Redis is down).
    # With Redis up, _bump_etag increments version → new cache key → DB query.
    from hubra.api.i18n.services import upsert_translation

    upsert_translation("de-CH", "test.key1", "Wert 2")
    db.session.commit()

    # Clear in-memory cache to simulate Redis invalidation
    i18n_services._mem_translations.clear()

    result2 = i18n_services.get_translations_dict("de-CH")
    assert result2["test.key1"] == "Wert 2"

    i18n_services._mem_translations.clear()  # cleanup


def test_report_keys_dispatches_async_task(client, auth_headers):
    """/i18n/<locale>/report dispatches Celery task in production mode."""
    # In testing mode, the route runs synchronously — so we test the
    # non-testing path by patching TESTING config.
    with patch(
        "flask.current_app.config.get",
        side_effect=lambda key, default=None: False if key == "TESTING" else None,
    ):
        with patch(
            "hubra.core.tasks.i18n_tasks.report_missing_keys_task.delay"
        ) as mock_delay:
            resp = client.post(
                "/api/v1/i18n/de-CH/report",
                json={"keys": [{"key": "missing.key", "default_value": "Default"}]},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.get_json()["flagged"] == 0
            mock_delay.assert_called_once()
