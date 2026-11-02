"""Upgrade tracking: notice new builds rolling out (services/upgrades.py)."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.upgrade_tasks.check_upgrades")
def check_upgrades() -> dict:
    from hubra.core.services import upgrades

    result = upgrades.check()
    db.session.commit()
    return result
