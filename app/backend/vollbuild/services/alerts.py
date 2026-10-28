"""Backwards-compatible re-export from vollbuild.core.services.alerts."""

from vollbuild.core.services.alerts import (
    Any,
    _log,
    COLOR_RED,
    COLOR_ORANGE,
    COLOR_GREEN,
    _get_webhook_url,
    send_alert,
    alert_error,
    alert_warning,
    alert_resolved,
)
