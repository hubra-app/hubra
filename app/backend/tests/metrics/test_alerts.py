"""
Tests for B3 — Discord alerting utility.

Covers:
  - Alert sent with correct payload format
  - Webhook URL not configured → returns False silently
  - HTTP errors don't propagate
  - Embed color variants (error, warning, resolved)
  - Fields included when provided
"""

from unittest.mock import patch, MagicMock


from vollbuild.core.services.alerts import (
    send_alert,
    alert_error,
    alert_warning,
    alert_resolved,
    COLOR_RED,
    COLOR_ORANGE,
    COLOR_GREEN,
)


class TestSendAlert:
    """Tests for the core send_alert function."""

    @patch("vollbuild.core.services.alerts._get_webhook_url")
    @patch("vollbuild.core.services.alerts.urllib.request.urlopen")
    def test_send_alert_success(self, mock_urlopen, mock_get_url):
        """Successful alert returns True."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = send_alert("Test Alert", "Something happened")
        assert result is True

    @patch("vollbuild.core.services.alerts._get_webhook_url")
    def test_webhook_not_configured(self, mock_get_url):
        """Missing webhook URL returns False silently."""
        mock_get_url.return_value = ""
        result = send_alert("Test", "msg")
        assert result is False

    @patch("vollbuild.core.services.alerts._get_webhook_url")
    @patch("vollbuild.core.services.alerts.urllib.request.urlopen")
    def test_http_error_doesnt_propagate(self, mock_urlopen, mock_get_url):
        """HTTP errors are caught and return False."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_urlopen.side_effect = Exception("Connection refused")

        result = send_alert("Test", "msg")
        assert result is False

    @patch("vollbuild.core.services.alerts._get_webhook_url")
    @patch("vollbuild.core.services.alerts.urllib.request.urlopen")
    def test_sends_correct_payload(self, mock_urlopen, mock_get_url):
        """Payload contains correct JSON structure."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        send_alert("My Title", "My Desc", color=COLOR_ORANGE)

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.method == "POST"
        assert req.get_header("Content-type") == "application/json"
        import json

        payload = json.loads(req.data)
        assert payload["embeds"][0]["title"] == "My Title"
        assert payload["embeds"][0]["description"] == "My Desc"
        assert payload["embeds"][0]["color"] == COLOR_ORANGE

    @patch("vollbuild.core.services.alerts._get_webhook_url")
    @patch("vollbuild.core.services.alerts.urllib.request.urlopen")
    def test_fields_included(self, mock_urlopen, mock_get_url):
        """Fields are included in the embed when provided."""
        mock_get_url.return_value = "https://discord.com/api/webhooks/test"
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        fields = [{"name": "Host", "value": "web01", "inline": True}]
        send_alert("Alert", "msg", fields=fields)

        import json

        payload = json.loads(mock_urlopen.call_args[0][0].data)
        assert payload["embeds"][0]["fields"][0]["name"] == "Host"
        assert payload["embeds"][0]["fields"][0]["value"] == "web01"
        assert payload["embeds"][0]["fields"][0]["inline"] is True


class TestAlertHelpers:
    """Tests for convenience functions."""

    @patch("vollbuild.core.services.alerts.send_alert")
    def test_alert_error_uses_red(self, mock_send):
        mock_send.return_value = True
        alert_error("Err", "desc")
        mock_send.assert_called_once_with("Err", "desc", color=COLOR_RED, fields=None)

    @patch("vollbuild.core.services.alerts.send_alert")
    def test_alert_warning_uses_orange(self, mock_send):
        mock_send.return_value = True
        alert_warning("Warn", "desc")
        mock_send.assert_called_once_with(
            "Warn", "desc", color=COLOR_ORANGE, fields=None
        )

    @patch("vollbuild.core.services.alerts.send_alert")
    def test_alert_resolved_uses_green(self, mock_send):
        mock_send.return_value = True
        alert_resolved("Fixed", "desc")
        mock_send.assert_called_once_with(
            "Fixed", "desc", color=COLOR_GREEN, fields=None
        )


class TestGetWebhookUrl:
    """Tests for _get_webhook_url."""

    @patch("vollbuild.core.services.alerts.os.environ")
    def test_falls_back_to_env(self, mock_environ):
        """Returns empty string when no Flask app and env var not set."""
        mock_environ.get.return_value = ""
        from vollbuild.core.services.alerts import _get_webhook_url

        # Force the RuntimeError path (no Flask app context)
        result = _get_webhook_url()
        assert result == ""
