"""Background jobs of the platform bot (``services.platform_bot``).

* ``tick`` (every minute): tells club servers when planned maintenance starts
  or ends, marks alerts resolved,
  installs /plattform and /wartung on the platform server, announces a new
  release, and once a day at 08:00 (platform time zone) posts the digest
  and the key-rotation reminder.
* ``approve_request``: Approve on a club request in Discord (setting the
  club up can take longer than Discord waits for an answer).
* ``post_security``: one security ping.
* ``club_notice``: release and maintenance notices to the clubs' servers.

None of them raise: a Discord problem is logged and must not turn into a
failed-task alert about itself.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)

DIGEST_HOUR = 8


def _step(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001
        _log.warning("platform bot tick: %s failed: %s", name, exc)
        try:
            from hubra.core.extensions import db

            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass


def _maintenance() -> None:
    from hubra.core.services import platform_bot

    # Windows start and end by themselves; club servers hear about it here.
    platform_bot.window_notices()


def _daily(now: datetime) -> None:
    from hubra.core.services import platform_bot, platform_discord

    local = now.astimezone(platform_bot._zone())
    if local.hour < DIGEST_HOUR:
        return
    channel, token = platform_discord._settings()
    if not channel or not token:
        return
    # Once per day, even with several workers.
    if not platform_bot._set(
        f"platform_bot:digest:{local:%Y-%m-%d}", "1", ex=2 * 24 * 3600, nx=True
    ):
        return
    _step("digest", platform_bot.send_digest, now)
    _step("keys", platform_bot.key_reminder, now)


@celery_app.task(name="hubra.core.tasks.platform_bot_tasks.tick", ignore_result=True)
def tick() -> None:
    from hubra.core.services import platform_bot, platform_discord

    now = datetime.now(timezone.utc)
    _step("maintenance", _maintenance)
    channel, token = platform_discord._settings()
    if not channel or not token:
        return
    _step("resolve alerts", platform_bot.resolve_alerts)
    _step("commands", platform_bot.register_commands)
    _step("release", platform_bot.announce_release)
    _step("daily", _daily, now)


@celery_app.task(
    name="hubra.core.tasks.platform_bot_tasks.approve_request", ignore_result=True
)
def approve_request(req_id: int, user_id: int, interaction_token: str = "") -> None:
    from hubra.core.services import platform_bot

    try:
        text = platform_bot.approve_now(int(req_id), int(user_id))
    except Exception:  # noqa: BLE001
        _log.exception("platform bot: approving request %s failed", req_id)
        from hubra.core.extensions import db

        db.session.rollback()
        text = "Das hat nicht geklappt; der Fehler ist im Log."
    platform_bot.follow_up(interaction_token, text)


@celery_app.task(
    name="hubra.core.tasks.platform_bot_tasks.post_security", ignore_result=True
)
def post_security(title: str, lines: list, level: str = "warning") -> None:
    from hubra.core.services import platform_bot

    try:
        platform_bot.post_security_now(title, list(lines), level)
    except Exception as exc:  # noqa: BLE001
        _log.warning("platform bot: security ping not posted: %s", exc)


@celery_app.task(
    name="hubra.core.tasks.platform_bot_tasks.club_notice", ignore_result=True
)
def club_notice(kind: str, payload: dict) -> None:
    from hubra.core.services import platform_bot

    try:
        sent = platform_bot.send_club_notices(kind, payload or {})
        _log.info("platform notice %s went to %s club servers", kind, sent)
    except Exception:  # noqa: BLE001
        _log.warning("platform bot: club notice %s failed", kind, exc_info=True)
