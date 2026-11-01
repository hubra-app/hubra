"""
Tests for system alerts (posted to the platform Discord log).

Covers:
  - Embed built with title, description, color and fields
  - Log not set up / no app context → returns False silently
  - Embed color variants (error, warning, resolved)

Posting itself is covered in tests/manager/test_platform_discord_log.py.
"""

from unittest.mock import patch


from hubra.core.services.alerts import (
    send_alert,
    alert_error,
    alert_warning,
    alert_resolved,
    COLOR_RED,
    COLOR_ORANGE,
    COLOR_GREEN,
)


class TestSendAlert:
    """send_alert builds an embed and hands it to the platform Discord log."""

    @patch("hubra.core.services.platform_discord.post_alert")
    def test_send_alert_success(self, post):
        post.return_value = True
        assert send_alert("Test Alert", "Something happened") is True

    @patch("hubra.core.services.platform_discord.post_alert")
    def test_log_not_set_up(self, post):
        post.return_value = False
        assert send_alert("Test", "msg") is False

    def test_no_app_context_does_not_raise(self):
        assert send_alert("Test", "msg") is False

    @patch("hubra.core.services.platform_discord.post_alert")
    def test_sends_correct_embed(self, post):
        send_alert("My Title", "My Desc", color=COLOR_ORANGE)
        embed = post.call_args.args[0]
        assert embed == {
            "title": "My Title",
            "description": "My Desc",
            "color": COLOR_ORANGE,
        }

    @patch("hubra.core.services.platform_discord.post_alert")
    def test_fields_included(self, post):
        fields = [{"name": "Host", "value": "web01", "inline": True}]
        send_alert("Alert", "msg", fields=fields)
        assert post.call_args.args[0]["fields"] == [
            {"name": "Host", "value": "web01", "inline": True}
        ]


class TestAlertHelpers:
    """Tests for convenience functions."""

    @patch("hubra.core.services.alerts.send_alert")
    def test_alert_error_uses_red(self, mock_send):
        mock_send.return_value = True
        alert_error("Err", "desc")
        mock_send.assert_called_once_with("Err", "desc", color=COLOR_RED, fields=None)

    @patch("hubra.core.services.alerts.send_alert")
    def test_alert_warning_uses_orange(self, mock_send):
        mock_send.return_value = True
        alert_warning("Warn", "desc")
        mock_send.assert_called_once_with(
            "Warn", "desc", color=COLOR_ORANGE, fields=None
        )

    @patch("hubra.core.services.alerts.send_alert")
    def test_alert_resolved_uses_green(self, mock_send):
        mock_send.return_value = True
        alert_resolved("Fixed", "desc")
        mock_send.assert_called_once_with(
            "Fixed", "desc", color=COLOR_GREEN, fields=None
        )


def test_the_alert_helpers_take_what_their_callers_pass():
    """Every caller (task failures, disk, Redis, Postgres) passes description=;
    the helpers took message=, so each alert raised TypeError instead."""
    with patch("hubra.core.services.alerts.send_alert") as send:
        alert_error(title="t", description="d", fields=[])
        alert_warning(title="t", description="d")
        alert_resolved(title="t", description="d")
    assert send.call_count == 3
