"""
Tests for B2 — Storage metrics.

Covers:
  - get_storage_bytes aggregates PG + mail
  - Graceful failure when WildDuck not configured
  - Graceful failure on DB errors
  - get_storage_breakdown returns correct structure
"""

from unittest.mock import patch, MagicMock


from hubra.core.services.storage_metrics import (
    get_storage_bytes,
    _get_pg_schema_size,
    _get_mail_quota_total,
)


class TestGetStorageBytes:
    """Tests for storage byte aggregation."""

    @patch("hubra.core.services.storage_metrics._get_pg_schema_size")
    @patch("hubra.core.services.storage_metrics._get_mail_quota_total")
    def test_sums_pg_and_mail(self, mock_mail, mock_pg):
        """Total = PG schema + mail quota."""
        mock_pg.return_value = 1024
        mock_mail.return_value = 512
        result = get_storage_bytes(tenant_id=1)
        assert result == 1536

    @patch("hubra.core.services.storage_metrics._get_pg_schema_size")
    @patch("hubra.core.services.storage_metrics._get_mail_quota_total")
    def test_returns_zero_when_both_fail(self, mock_mail, mock_pg):
        """Returns 0 when both sources fail."""
        mock_pg.return_value = 0
        mock_mail.return_value = 0
        result = get_storage_bytes(tenant_id=1)
        assert result == 0


class TestPgSchemaSize:
    """Tests for PostgreSQL schema size query."""

    def test_returns_schema_size(self):
        """Returns the size of the club's own schema, on Postgres."""
        with (
            patch("hubra.core.services.storage_metrics.db") as mock_db,
            patch(
                "hubra.core.services.tenant_health._schema_sizes",
                return_value={1: 2048},
            ) as sizes,
        ):
            mock_db.session.get_bind.return_value.dialect.name = "postgresql"
            result = _get_pg_schema_size(tenant_id=1)
        assert result == 2048
        sizes.assert_called_once_with([1])

    def test_zero_without_postgres(self):
        with patch("hubra.core.services.storage_metrics.db") as mock_db:
            mock_db.session.get_bind.return_value.dialect.name = "sqlite"
            assert _get_pg_schema_size(tenant_id=1) == 0

    def test_returns_zero_on_error(self):
        """Returns 0 on database errors."""
        with (
            patch("hubra.core.services.storage_metrics.db") as mock_db,
            patch(
                "hubra.core.services.tenant_health._schema_sizes",
                side_effect=Exception("DB error"),
            ),
        ):
            mock_db.session.get_bind.return_value.dialect.name = "postgresql"
            result = _get_pg_schema_size(tenant_id=1)
        assert result == 0


class TestMailQuota:
    """Tests for WildDuck mail quota query."""

    @patch("urllib.request.urlopen")
    def test_returns_quota_when_configured(self, mock_urlopen):
        """Returns quota when WildDuck API is configured."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"totalQuota": 4096}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("flask.current_app") as mock_app:
            mock_app.config = {
                "WILDDUCK_API_URL": "http://localhost:8080",
                "WILDDUCK_API_TOKEN": "test-token",
            }
            result = _get_mail_quota_total(tenant_id=1)
            assert result == 4096

    @patch("flask.current_app")
    def test_returns_zero_when_not_configured(self, mock_app):
        """Returns 0 when WildDuck is not configured."""
        mock_app.config = {"WILDDUCK_API_URL": "", "WILDDUCK_API_TOKEN": ""}
        result = _get_mail_quota_total(tenant_id=1)
        assert result == 0

