"""Plugin housekeeping: the update check and staged archives nobody confirmed."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.plugin_tasks.check_plugin_updates")
def check_plugin_updates() -> dict:
    from hubra.core.plugins.installer import cleanup_archives
    from hubra.core.plugins.updates import check

    from hubra.core.services import platform_monitor

    cleanup_archives()
    db.session.commit()
    result = check()
    platform_monitor.plugin_news(result)
    return result


@celery_app.task(name="hubra.core.tasks.plugin_tasks.usage_snapshot", ignore_result=True)
def usage_snapshot() -> None:
    """Nightly: which clubs use which modules and plugins (manage › Plugins ›
    Nutzung, ``services.module_usage``)."""
    from hubra.core.services import module_usage

    module_usage.refresh()
