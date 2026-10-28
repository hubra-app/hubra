"""Backwards-compatible re-export from vollbuild.core.services.wildduck."""

from vollbuild.core.services.wildduck import (
    annotations,
    Any,
    current_app,
    logger,
    _RETRY_CONFIG,
    WildDuckError,
    WildDuckClient,
    get_client,
    try_get_client,
    make_username,
    apply_email_schema,
)
