"""Tests for @require_tenant_feature decorator.

Tests the decorator logic directly without needing to register a blueprint
on the already-started Flask app.
"""

from unittest.mock import MagicMock, patch

from vollbuild.api.permissions import require_tenant_feature


def _call_decorator(feature_enabled: bool):
    """Invoke the decorator with a mocked Flask context.

    Returns the (status_code, json) tuple the decorator produces.
    """
    decorator = require_tenant_feature("test_feature")

    @decorator
    def handler():
        return {"ok": True}, 200

    with (
        patch("vollbuild.api.permissions.verify_jwt_in_request"),
        patch(
            "vollbuild.api.features.services.FeatureFlagService.is_enabled",
            return_value=feature_enabled,
        ),
    ):
        result = handler()
        if isinstance(result, tuple):
            response = MagicMock()
            response.status_code = result[1]
            response.get_json.return_value = result[0]
            return response
        return result


def test_require_tenant_feature_passes_when_enabled():
    """Feature enabled → handler called, returns 200."""
    resp = _call_decorator(True)
    assert resp.status_code == 200


def test_require_tenant_feature_blocks_when_disabled():
    """Feature disabled → 403 FEATURE_DISABLED."""
    resp = _call_decorator(False)
    assert resp.status_code == 403
