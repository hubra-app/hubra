"""Support cases on Discord: one private thread per case.

Set up in manage › Discord › Kanäle: a support channel on the platform's
Discord server (``discord.support_channel_id``).  Then:

* Every new case gets a private thread in that channel, opened by the Hubra
  bot with the case as its first message (title, text, kind, club, page;
  never an e-mail address).  Staff open a thread for an older case in
  manage › Meldungen & Ideen.
* The reporter is added to the thread when their account linked Discord
  (``discord.support_add_reporters``, on by default), and so is everyone
  staff add to the case (``support_case_people``).  Someone who is not on
  the platform server yet gets a one-time invite (7 days) as a direct
  message; once they joined, the tick adds them to the thread.
* The tick (every minute, ``platform_bot_tasks.tick``) reads new messages of
  the threads into the case's comments: from staff (``support.cases``) as an
  answer, from the reporter or an added person as their own comment, from
  anyone else as an internal note.  A staff message that starts with ``//``
  stays an internal note.  People on the case who are not in the thread
  hear about a staff answer by mail, like an answer from manage.
* Comments written in manage or on the support site go into the thread
  (internal notes never do), and so do status changes.  A done or closed
  case archives its thread; writing in it again opens it.

Reading messages needs the Message Content intent of the Discord
application (Developer Portal › Bot), and the bot needs View Channel, Send
Messages, Send Messages in Threads, Create Private Threads, Manage Threads,
Read Message History and Create Invite in the support channel.

Everything that talks to Discord runs in a background job; a Discord
problem is logged and never fails the request that queued it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.support_case import (
    SupportCase,
    SupportCaseComment,
    SupportCasePerson,
)
from hubra.core.models.user import User

_log = logging.getLogger(__name__)

CHANNEL_KEY = "discord.support_channel_id"
ADD_REPORTERS_KEY = "discord.support_add_reporters"
INVITE_DAYS = 7
INTERNAL_PREFIX = "//"
# Message types that are something a person wrote (default, reply).
_TEXT_TYPES = (0, 19)
PRIVATE_THREAD = 12
ARCHIVE_MINUTES = 10080  # a week without messages

KIND_COLORS = {"bug": 0xE74C3C, "feature": 0xD4A72C, "question": 0x6D4AFF}
KIND_LABELS = {"bug": "Problem", "feature": "Idee", "question": "Frage"}
STATUS_LABELS = {
    "open": "Offen",
    "planned": "Geplant",
    "in_progress": "In Arbeit",
    "done": "Erledigt",
    "closed": "Geschlossen",
}

# Where a person stands in the case's thread (``SupportCasePerson.discord``).
ADDED, INVITED, NO_DISCORD, FAILED = "added", "invited", "no_discord", "failed"


# ── Settings ──────────────────────────────────────────────────────────────────


def channel_id() -> str:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get(CHANNEL_KEY) or ""
    except Exception:  # noqa: BLE001
        return ""


def enabled() -> bool:
    """A support channel and a bot token are set."""
    from hubra.core.services import platform_bot

    try:
        return bool(channel_id() and platform_bot._token())
    except Exception:  # noqa: BLE001
        return False


def add_reporters() -> bool:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get(ADD_REPORTERS_KEY) != "off"
    except Exception:  # noqa: BLE001
        return True


def _bot(method: str, path: str, body=None):
    from hubra.core.services import platform_bot

    return platform_bot._bot(method, path, body)


def guild_id() -> str:
    """The server the support channel is on (cached for an hour), or ""."""
    from hubra.core.services import platform_bot

    channel = channel_id()
    if not channel:
        return ""
    key = f"support_discord:guild:{channel}"
    cached = platform_bot._get(key)
    if cached is not None:
        return cached
    try:
        guild = str((_bot("GET", f"/channels/{channel}") or {}).get("guild_id") or "")
    except platform_bot.BotError:
        _log.info("support threads: cannot read the support channel", exc_info=True)
        return ""
    platform_bot._set(key, guild, ex=3600)
    return guild


def _cached_guild() -> str:
    """The guild id if it is known already (no call to Discord)."""
    from hubra.core.services import platform_bot

    channel = channel_id()
    return (platform_bot._get(f"support_discord:guild:{channel}") or "") if channel else ""


def thread_url(case: SupportCase) -> str | None:
    if not case.discord_thread_id:
        return None
    guild = _cached_guild()
    if not guild:
        return None
    return f"https://discord.com/channels/{guild}/{case.discord_thread_id}"


def invite_url(person: SupportCasePerson) -> str | None:
    return f"https://discord.gg/{person.invite_code}" if person.invite_code else None


# ── Who is on a case ──────────────────────────────────────────────────────────


def people(case: SupportCase) -> list[SupportCasePerson]:
    return list(
        db.session.scalars(
            select(SupportCasePerson)
            .where(SupportCasePerson.case_id == case.id)
            .order_by(SupportCasePerson.created_at, SupportCasePerson.id)
        ).all()
    )


def person_ids(case: SupportCase) -> set[int]:
    """The reporter and everyone added to the case."""
    ids = set(
        db.session.scalars(
            select(SupportCasePerson.user_id).where(
                SupportCasePerson.case_id == case.id
            )
        ).all()
    )
    if case.user_id:
        ids.add(case.user_id)
    return ids


def people_dicts(case: SupportCase) -> list[dict]:
    """manage: the reporter first, then everyone added, with where they
    stand in the Discord thread."""
    from hubra.core.notifications import account_dm

    rows = {p.user_id: p for p in people(case)}
    ids = ([case.user_id] if case.user_id else []) + [
        uid for uid in rows if uid != case.user_id
    ]
    users = (
        {u.id: u for u in db.session.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    out = []
    for uid in ids:
        user = users.get(uid)
        if user is None:
            continue
        row = rows.get(uid)
        out.append(
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "reporter": uid == case.user_id,
                "added": row is not None,
                "discordLinked": account_dm.discord_id(uid) is not None,
                "discord": row.discord if row else "",
                "inviteUrl": invite_url(row) if row else None,
                "addedAt": row.created_at.isoformat() if row else None,
            }
        )
    return out


def add_people(case: SupportCase, user_ids: list[int], actor_id: int | None) -> list[int]:
    """Add accounts to the case (the reporter too, which puts them in the
    Discord thread).  Returns the ids that were new.  Flushes, no commit."""
    have = {p.user_id for p in people(case)}
    wanted = [uid for uid in dict.fromkeys(user_ids) if uid not in have]
    if not wanted:
        return []
    found = set(
        db.session.scalars(
            select(User.id)
            .where(User.id.in_(wanted))
            .where(User.is_disabled.is_(False))
        ).all()
    )
    added = [uid for uid in wanted if uid in found]
    for uid in added:
        db.session.add(SupportCasePerson(case_id=case.id, user_id=uid, added_by=actor_id))
    db.session.flush()
    return added


def remove_person(case: SupportCase, user_id: int) -> str | None:
    """Take someone off the case.  Returns their Discord id when they were
    in the thread (to take them out there too), else None."""
    from hubra.core.notifications import account_dm

    row = db.session.scalar(
        select(SupportCasePerson).where(
            SupportCasePerson.case_id == case.id,
            SupportCasePerson.user_id == user_id,
        )
    )
    if row is None:
        raise LookupError("not on the case")
    was_in = row.discord == ADDED
    db.session.delete(row)
    db.session.flush()
    return account_dm.discord_id(user_id) if was_in else None


def search_accounts(query: str, limit: int = 10) -> list[dict]:
    """Accounts by name or e-mail, for adding to a case."""
    from sqlalchemy import func, or_

    query = (query or "").strip()
    if len(query) < 2:
        return []
    like = f"%{query.lower()}%"
    full = func.lower(User.first_name + " " + User.last_name)
    rows = db.session.scalars(
        select(User)
        .where(User.is_disabled.is_(False))
        .where(or_(func.lower(User.email).like(like), full.like(like)))
        .order_by(User.last_name, User.first_name, User.id)
        .limit(limit)
    ).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in rows]


def in_thread(case: SupportCase) -> set[int]:
    """Accounts that are in the case's Discord thread."""
    return set(
        db.session.scalars(
            select(SupportCasePerson.user_id).where(
                SupportCasePerson.case_id == case.id,
                SupportCasePerson.discord == ADDED,
            )
        ).all()
    )


# ── Queueing (after the commit, from requests) ────────────────────────────────


def _queue(name: str, *args) -> None:
    if not enabled():
        return
    try:
        from hubra.core.tasks import support_discord_tasks as tasks

        # Support cases live in the public schema: no club context.
        getattr(tasks, name).apply_async(args=args, headers={"tenant_id": None})
    except Exception:  # noqa: BLE001
        _log.warning("support threads: could not queue %s", name, exc_info=True)


def case_created(case: SupportCase) -> None:
    _queue("open_thread", case.id)


def comment_added(comment: SupportCaseComment) -> None:
    if comment.internal or comment.discord_message_id:
        return
    _queue("mirror_comment", comment.id)


def status_changed(case: SupportCase) -> None:
    if case.discord_thread_id:
        _queue("mirror_status", case.id)


def people_added(case: SupportCase, user_ids: list[int]) -> None:
    if user_ids and case.discord_thread_id:
        _queue("join_people", case.id, list(user_ids))


def person_removed(case: SupportCase, discord_user: str | None) -> None:
    if discord_user and case.discord_thread_id:
        _queue("leave_thread", case.id, discord_user)


def open_now(case: SupportCase) -> None:
    _queue("open_thread", case.id)


# ── Talking to Discord (background jobs) ──────────────────────────────────────


def _plain(value, limit: int = 100) -> str:
    from hubra.core.services import platform_bot

    return platform_bot.plain(value, limit)


def _manage_link(case: SupportCase) -> str:
    from hubra.core.services import platform_bot

    return platform_bot._manage_url(f"/app/reports/{case.id}")


def starter_embed(case: SupportCase) -> dict:
    from hubra.core.services import support

    club = support._clubs({case.tenant_id}).get(case.tenant_id) if case.tenant_id else None
    reporter = db.session.get(User, case.user_id) if case.user_id else None
    fields = [
        {"name": "Art", "value": KIND_LABELS.get(case.kind, case.kind), "inline": True},
        {
            "name": "Status",
            "value": STATUS_LABELS.get(case.status, case.status),
            "inline": True,
        },
    ]
    if case.severity:
        fields.append({"name": "Dringlichkeit", "value": case.severity, "inline": True})
    if reporter is not None:
        fields.append({"name": "Von", "value": _plain(reporter.name), "inline": True})
    if club:
        fields.append({"name": "Verein", "value": _plain(club["name"]), "inline": True})
    if case.page:
        fields.append({"name": "Seite", "value": _plain(case.page, 300), "inline": False})
    details = case.details or {}
    for key, label in (("steps", "Schritte"), ("expected", "Erwartet"), ("useCase", "Wofür")):
        if details.get(key):
            fields.append({"name": label, "value": str(details[key])[:1000]})
    embed = {
        "title": f"#{case.id} {case.title}"[:256],
        "description": case.description[:3000],
        "color": KIND_COLORS.get(case.kind, 0x6D4AFF),
        "fields": fields[:25],
        "footer": {
            "text": "Was hier geschrieben wird, kommt als Kommentar zum Fall. "
            "Eine Nachricht des Teams mit // am Anfang bleibt eine interne Notiz."
        },
    }
    link = _manage_link(case)
    if link:
        embed["url"] = link
    return embed


def _post(case: SupportCase, body: dict) -> dict:
    """Post in the case's thread; opens an archived thread first."""
    from hubra.core.services.platform_bot import BotError

    body = {"allowed_mentions": {"parse": []}, **body}
    path = f"/channels/{case.discord_thread_id}/messages"
    try:
        return _bot("POST", path, body) or {}
    except BotError as exc:
        if exc.status not in (400, 403):
            raise
    _bot("PATCH", f"/channels/{case.discord_thread_id}", {"archived": False})
    return _bot("POST", path, body) or {}


def open_thread(case_id: int) -> bool:
    """Open the case's thread (once), post the case and add its people."""
    from hubra.core.services import platform_bot

    case = db.session.get(SupportCase, case_id)
    if case is None or case.discord_thread_id or case.merged_into_id is not None:
        return False
    channel = channel_id()
    if not channel or not platform_bot._token():
        return False
    if not platform_bot._set(f"support_discord:open:{case.id}", "1", ex=300, nx=True):
        return False
    try:
        thread = _bot(
            "POST",
            f"/channels/{channel}/threads",
            {
                "name": f"#{case.id} {case.title}"[:100],
                "type": PRIVATE_THREAD,
                "invitable": False,
                "auto_archive_duration": ARCHIVE_MINUTES,
            },
        )
    except platform_bot.BotError:
        platform_bot._delete(f"support_discord:open:{case.id}")
        raise
    case.discord_thread_id = str((thread or {}).get("id") or "") or None
    if not case.discord_thread_id:
        return False
    guild_id()  # known from now on, for the link in manage
    link = _manage_link(case)
    message = _post(
        case,
        {
            "embeds": [starter_embed(case)],
            **(
                {"components": [{"type": 1, "components": [platform_bot._link("In manage öffnen", link)]}]}
                if link
                else {}
            ),
        },
    )
    case.discord_last_message_id = str(message.get("id") or "") or case.discord_thread_id
    db.session.commit()
    if add_reporters() and case.user_id:
        add_people(case, [case.user_id], None)
        db.session.commit()
    join_all(case)
    return True


def join_all(case: SupportCase, user_ids: list[int] | None = None) -> None:
    """Put the case's people (or *user_ids* of them) in its thread."""
    for row in people(case):
        if user_ids is not None and row.user_id not in user_ids:
            continue
        try:
            join(case, row)
        except Exception:  # noqa: BLE001
            _log.warning(
                "support threads: user %s not added to case %s",
                row.user_id,
                case.id,
                exc_info=True,
            )
            row.discord = FAILED
        db.session.commit()


def _on_server(guild: str, discord_user: str) -> bool:
    from hubra.core.services.platform_bot import BotError

    try:
        _bot("GET", f"/guilds/{guild}/members/{discord_user}")
        return True
    except BotError as exc:
        if exc.status == 404:
            return False
        raise


def join(case: SupportCase, row: SupportCasePerson) -> str:
    """Add one person to the thread, or invite them to the server first.
    Returns their new state."""
    from hubra.core.notifications import account_dm
    from hubra.core.services import platform_discord

    discord_user = account_dm.discord_id(row.user_id)
    if not discord_user:
        row.discord = NO_DISCORD
        return row.discord
    if not case.discord_thread_id:
        row.discord = ""
        return row.discord
    guild = guild_id()
    if not guild:
        row.discord = FAILED
        return row.discord
    if _on_server(guild, discord_user):
        _bot("PUT", f"/channels/{case.discord_thread_id}/thread-members/{discord_user}")
        row.discord = ADDED
        row.invite_code = None
        return row.discord
    if row.discord == INVITED and row.invite_code:
        return row.discord
    invite = _bot(
        "POST",
        f"/channels/{channel_id()}/invites",
        {"max_age": INVITE_DAYS * 86400, "max_uses": 1, "unique": True},
    )
    row.invite_code = str((invite or {}).get("code") or "") or None
    row.discord = INVITED
    if row.invite_code:
        try:
            platform_discord.dm(
                discord_user,
                {
                    "title": f"Support-Fall #{case.id}: {case.title}"[:256],
                    "description": (
                        "Das Hubra-Team bespricht diesen Fall auf Discord. Tritt dem "
                        "Server mit der Einladung bei; danach kommst du automatisch "
                        f"in den Thread des Falls. Die Einladung gilt {INVITE_DAYS} Tage."
                    ),
                    "color": KIND_COLORS.get(case.kind, 0x6D4AFF),
                },
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "style": 5,
                                "label": "Server beitreten",
                                "url": invite_url(row),
                            }
                        ],
                    }
                ],
            )
        except Exception:  # noqa: BLE001
            # No shared server, or direct messages off: staff pass the link on.
            _log.info("support threads: invite DM to %s not delivered", row.user_id)
    return row.discord


def leave(case: SupportCase, discord_user: str) -> None:
    from hubra.core.services.platform_bot import BotError

    try:
        _bot(
            "DELETE",
            f"/channels/{case.discord_thread_id}/thread-members/{discord_user}",
        )
    except BotError as exc:
        if exc.status != 404:
            raise


def _author_label(case: SupportCase, comment: SupportCaseComment) -> str:
    if comment.from_staff:
        return "Team"
    if comment.user_id == case.user_id:
        return "meldende Person"
    return "beteiligt"


def mirror_comment(comment_id: int) -> bool:
    """A comment from manage or the support site goes into the thread."""
    comment = db.session.get(SupportCaseComment, comment_id)
    if comment is None or comment.internal or comment.discord_message_id:
        return False
    case = db.session.get(SupportCase, comment.case_id)
    if case is None or not case.discord_thread_id:
        return False
    author = db.session.get(User, comment.user_id) if comment.user_id else None
    name = _plain(author.name if author else "Hubra", 80)
    head = f"**{name}** · {_author_label(case, comment)}\n"
    message = _post(case, {"content": (head + comment.body)[:2000]})
    comment.discord_message_id = str(message.get("id") or "") or None
    db.session.commit()
    return True


def mirror_status(case_id: int) -> bool:
    """A new status (or a merge) goes into the thread; done and closed
    archive it."""
    from hubra.core.services import support

    case = db.session.get(SupportCase, case_id)
    if case is None or not case.discord_thread_id:
        return False
    if case.merged_into_id is not None:
        target = db.session.get(SupportCase, case.merged_into_id)
        text = f"Zusammengeführt mit #{case.merged_into_id}" + (
            f": {target.title}" if target else ""
        )
    else:
        text = f"Status: {STATUS_LABELS.get(case.status, case.status)}"
    _post(
        case,
        {
            "embeds": [
                {
                    "description": _plain(text, 300),
                    "color": 0x2ECC71 if case.status == "done" else 0x6D4AFF,
                }
            ]
        },
    )
    if case.status in support.FINISHED:
        _bot("PATCH", f"/channels/{case.discord_thread_id}", {"archived": True})
    return True


# ── Reading the threads (tick) ────────────────────────────────────────────────


def _is_staff(user: User) -> bool:
    from hubra.core.permissions import get_user_global_permissions

    if user.is_superadmin:
        return True
    keys = get_user_global_permissions(user.id)
    return "*" in keys or "support.cases" in keys


def _account_for(discord_user: str) -> User | None:
    from hubra.core.models.connected_app import ExternalAccount

    uid = db.session.scalar(
        select(ExternalAccount.user_id).where(
            ExternalAccount.provider == "discord",
            ExternalAccount.external_id == str(discord_user),
        )
    )
    user = db.session.get(User, uid) if uid else None
    return user if user is not None and not user.is_disabled else None


def _text_of(message: dict) -> str:
    parts = [str(message.get("content") or "").strip()]
    for item in message.get("attachments") or []:
        if isinstance(item, dict) and item.get("url"):
            parts.append(str(item["url"]))
    return "\n".join(p for p in parts if p).strip()


def import_message(case: SupportCase, message: dict) -> SupportCaseComment | None:
    """One Discord message → one comment (see the module docstring)."""
    from hubra.core.services import support

    author = message.get("author") or {}
    if author.get("bot") or message.get("type", 0) not in _TEXT_TYPES:
        return None
    message_id = str(message.get("id") or "")
    if not message_id:
        return None
    if db.session.scalar(
        select(SupportCaseComment.id).where(
            SupportCaseComment.discord_message_id == message_id
        )
    ):
        return None
    body = _text_of(message)
    if not body:
        return None
    user = _account_for(str(author.get("id") or ""))
    on_case = user is not None and user.id in person_ids(case)
    staff = internal = False
    if user is not None and not on_case and _is_staff(user):
        staff = True
        if body.startswith(INTERNAL_PREFIX):
            internal = True
            body = body[len(INTERNAL_PREFIX) :].strip()
    elif not on_case:
        # Someone else who can see the channel: a note for the team.
        staff = internal = True
        who = user.name if user else (author.get("global_name") or author.get("username"))
        body = f"{who or 'Discord'} (Discord): {body}"
    if not body:
        return None
    comment = SupportCaseComment(
        case_id=case.id,
        user_id=user.id if user else None,
        body=body[: support.COMMENT_MAX],
        from_staff=staff,
        internal=internal,
        discord_message_id=message_id,
    )
    db.session.add(comment)
    case.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return comment


def read_thread(case: SupportCase) -> int:
    """Read the thread's new messages into comments.  Returns how many."""
    from hubra.core.services import support

    after = case.discord_last_message_id or case.discord_thread_id
    messages = _bot(
        "GET", f"/channels/{case.discord_thread_id}/messages?after={after}&limit=100"
    )
    if not isinstance(messages, list):
        return 0
    answers: list[SupportCaseComment] = []
    count = 0
    for message in sorted(messages, key=lambda m: int(m.get("id") or 0)):
        case.discord_last_message_id = str(message.get("id"))
        comment = import_message(case, message)
        if comment is None:
            continue
        count += 1
        if comment.from_staff and not comment.internal:
            answers.append(comment)
    db.session.commit()
    if answers:
        there = in_thread(case)
        away = [u for u in support.followers(case) if u.id not in there]
        for comment in answers:
            if away:
                support.mail_update(case, away, comment=comment.body)
    return count


def sync() -> int:
    """The tick: pending invites, then new messages of active threads."""
    from hubra.core.services import platform_bot

    if not enabled():
        return 0
    if not platform_bot._set("support_discord:sync", "1", ex=50, nx=True):
        return 0
    _retry_invites()
    guild = guild_id()
    if not guild:
        return 0
    data = _bot("GET", f"/guilds/{guild}/threads/active") or {}
    channel = channel_id()
    latest = {
        str(t.get("id")): str(t.get("last_message_id") or "")
        for t in data.get("threads") or []
        if str(t.get("parent_id") or "") == channel
    }
    if not latest:
        return 0
    cases = db.session.scalars(
        select(SupportCase).where(SupportCase.discord_thread_id.in_(list(latest)))
    ).all()
    total = 0
    for case in cases:
        newest = latest.get(case.discord_thread_id or "")
        if not newest or newest == case.discord_last_message_id:
            continue
        try:
            total += read_thread(case)
        except Exception:  # noqa: BLE001
            db.session.rollback()
            _log.warning("support threads: case %s not read", case.id, exc_info=True)
    return total


def _retry_invites() -> None:
    since = datetime.now(timezone.utc) - timedelta(days=INVITE_DAYS + 1)
    rows = db.session.scalars(
        select(SupportCasePerson)
        .where(SupportCasePerson.discord == INVITED)
        .where(SupportCasePerson.created_at >= since)
        .limit(50)
    ).all()
    for row in rows:
        case = db.session.get(SupportCase, row.case_id)
        if case is None or not case.discord_thread_id:
            continue
        try:
            join(case, row)
        except Exception:  # noqa: BLE001
            _log.info("support threads: invite of %s not checked", row.user_id)
        db.session.commit()
