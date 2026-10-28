"""Backwards-compatible re-export from vollbuild.core.services.mail_i18n."""

from vollbuild.core.services.mail_i18n import (
    annotations,
    datetime,
    timezone,
    render_template,
    Markup,
    escape,
    logger,
    _FALLBACK_CHAIN,
    get_mail_translator,
    _touch_last_used,
    render_mail_template,
)
