"""Plugin housekeeping: the update check and staged archives nobody confirmed."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.plugin_tasks.check_plugin_updates")
def check_plugin_updates() -> dict:
    from hubra.core.plugins.installer import cleanup_archives
    from hubra.core.plugins.updates import check

    cleanup_archives()
    db.session.commit()
    return check()
