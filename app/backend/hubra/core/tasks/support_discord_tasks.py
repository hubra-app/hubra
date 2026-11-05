"""Background jobs of the support threads on Discord
(``services.support_discord``).  The messages of the threads are read by the
platform bot's tick (``platform_bot_tasks.tick``).

None of them raise: a Discord problem is logged and must not turn into a
failed-task alert about itself.
"""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)


def _run(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception:  # noqa: BLE001
        _log.warning("support threads: %s failed", name, exc_info=True)
        from hubra.core.extensions import db

        db.session.rollback()


@celery_app.task(
    name="hubra.core.tasks.support_discord_tasks.open_thread", ignore_result=True
)
def open_thread(case_id: int) -> None:
    from hubra.core.services import support_discord

    _run("open_thread", support_discord.open_thread, int(case_id))


@celery_app.task(
    name="hubra.core.tasks.support_discord_tasks.mirror_comment", ignore_result=True
)
def mirror_comment(comment_id: int) -> None:
    from hubra.core.services import support_discord

    _run("mirror_comment", support_discord.mirror_comment, int(comment_id))


@celery_app.task(
    name="hubra.core.tasks.support_discord_tasks.mirror_status", ignore_result=True
)
def mirror_status(case_id: int) -> None:
    from hubra.core.services import support_discord

    _run("mirror_status", support_discord.mirror_status, int(case_id))


def _join(case_id: int, user_ids: list) -> None:
    from hubra.core.extensions import db
    from hubra.core.models.support_case import SupportCase
    from hubra.core.services import support_discord

    case = db.session.get(SupportCase, case_id)
    if case is not None and case.discord_thread_id:
        support_discord.join_all(case, [int(u) for u in user_ids])


@celery_app.task(
    name="hubra.core.tasks.support_discord_tasks.join_people", ignore_result=True
)
def join_people(case_id: int, user_ids: list) -> None:
    _run("join_people", _join, int(case_id), list(user_ids or []))


def _leave(case_id: int, discord_user: str) -> None:
    from hubra.core.extensions import db
    from hubra.core.models.support_case import SupportCase
    from hubra.core.services import support_discord

    case = db.session.get(SupportCase, case_id)
    if case is not None and case.discord_thread_id:
        support_discord.leave(case, discord_user)


@celery_app.task(
    name="hubra.core.tasks.support_discord_tasks.leave_thread", ignore_result=True
)
def leave_thread(case_id: int, discord_user: str) -> None:
    _run("leave_thread", _leave, int(case_id), str(discord_user))
