"""Post-deploy steps on the default queue (services/post_deploy.py).

Not a platform task module (``roles.PLATFORM_TASK_MODULES``): the club
worker loads the club routes and plugins that ``sync-permissions`` and
``plugins sync`` read, a platform worker does not.
"""

from __future__ import annotations

from hubra.core.tasks import celery_app

# How often to look again while a worker on the old build took the task.
RETRY_SECONDS = 60
MAX_RETRIES = 30


@celery_app.task(
    name="hubra.core.tasks.post_deploy_tasks.run_post_deploy_steps",
    bind=True,
    max_retries=MAX_RETRIES,
)
def run_post_deploy_steps(
    self,
    build_key: str | None = None,
    trigger: str = "deploy",
    actor_id: int | None = None,
) -> dict:
    from hubra.core import build_info
    from hubra.core.services import post_deploy, upgrades

    own = upgrades.build_key(
        {"commit": build_info.commit(), "version": build_info.version()}
    )
    if build_key and own != build_key:
        # A worker still on the old build: the new one runs the new migrations.
        raise self.retry(countdown=RETRY_SECONDS)
    if trigger != "manual" and build_key and post_deploy.ran_for(build_key):
        return {"state": "already"}
    # "locked": an init step holds the lock and does the same work.
    return post_deploy.run(build_key, trigger=trigger, actor_id=actor_id)
