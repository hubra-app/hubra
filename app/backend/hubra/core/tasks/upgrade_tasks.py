"""Upgrade tracking: notice new builds rolling out (services/upgrades.py)."""

from __future__ import annotations

from hubra.core.extensions import db
from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.upgrade_tasks.check_upgrades")
def check_upgrades() -> dict:
    from hubra.core.services import upgrades

    result = upgrades.check()
    db.session.commit()
    if result.get("state") in ("done", "baseline"):
        # Every process runs the new build: run migrations, seeds and the
        # permission sync once (services/post_deploy.py).
        from hubra.core.services import post_deploy
        from hubra.core.tasks.post_deploy_tasks import run_post_deploy_steps

        if post_deploy.enabled():
            run_post_deploy_steps.delay(upgrades.build_key(result["build"]))
    return result
