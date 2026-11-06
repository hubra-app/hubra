"""Which notifications a member wants, per topic and channel.

Each notification belongs to a topic (new posts, reminders, my sign-ups...).
Per topic a member turns the bell (in Hubra) and browser push on or off, and
mail where Hubra mails that topic (the reminders).  Everything is on until the
member turns it off.  A notification without a topic (a sign-in from a new
device, a notice to the club's owners) always comes.

Bell and push are stored in ``members.notify_prefs``; the reminder mails keep
their own columns (``event_reminder_mail``, ``poll_reminder_mail``).

A connected app that delivers notifications (a Discord direct message, see
``channels``) is one more channel, named after its code. It is off until the
member turns it on, and never carries a notification without a topic.  It
does not depend on the bell: a member can have a topic as a direct message
only.  One switch on the account (``users.dm_prefs.muted``, see
``account_dm``) stops every direct message.

Some topics have other defaults or fewer channels: the confirmation of a
member's own sign-up (``bookings``) is off in the bell and push until turned
on, and the weekly digest (``digest``) goes by mail or as a direct message
only.
"""

from __future__ import annotations

TOPICS = (
    "posts",
    "events",
    "polls",
    "event_reminders",
    "poll_reminders",
    "my_events",
    "bookings",
    "waitlist",
    "my_polls",
    "tasks",
    "requests",
    "payments",
    "membership",
    "qualifications",
    "digest",
)
CHANNELS = ("bell", "push")
# Topics that also go by mail, and the member column that switches it.
MAIL_COLUMNS = {
    "event_reminders": "event_reminder_mail",
    "poll_reminders": "poll_reminder_mail",
    "digest": "weekly_digest_mail",
}
# Topics without the bell and push (they are no bell notification).
NO_BELL = ("digest",)
# Bell and push off until the member turns them on (their own doing).
QUIET = ("bookings",)


def default(channel: str, topic: str | None = None) -> bool:
    """Bell and push are on until turned off (except ``QUIET`` topics); app
    channels are off."""
    return channel in CHANNELS and topic not in QUIET


def channels_for(topic: str, apps: list[str] | tuple[str, ...] = ()) -> tuple:
    """The channels *topic* has, mail aside."""
    return (() if topic in NO_BELL else CHANNELS) + tuple(apps)


def wants(stored: dict | None, topic: str | None, channel: str) -> bool:
    """Whether a member with ``notify_prefs`` *stored* gets *topic* on
    *channel*.  No topic: always on the bell and push, never on an app."""
    if not topic:
        return channel in CHANNELS
    if topic in NO_BELL and channel in CHANNELS:
        return False
    value = ((stored or {}).get(topic) or {}).get(channel, default(channel, topic))
    return value is True


def prefs_for(member, apps: list[str] | tuple[str, ...] = ()) -> dict[str, dict[str, bool]]:
    """Per topic and channel. *apps*: the app channels the member has
    (``channels.available``)."""
    out: dict[str, dict[str, bool]] = {}
    for topic in TOPICS:
        row = {c: wants(member.notify_prefs, topic, c) for c in channels_for(topic, apps)}
        if topic in MAIL_COLUMNS:
            row["mail"] = bool(getattr(member, MAIL_COLUMNS[topic]))
        out[topic] = row
    return out


def validate(body, apps: list[str] | tuple[str, ...] = ()) -> str | None:
    """Error text for a body of ``{topic: {channel: bool}}``, or None."""
    if not isinstance(body, dict) or not body:
        return "Expected an object of topics"
    for topic, channels in body.items():
        if topic not in TOPICS:
            return f"Unknown topic: {topic}"
        allowed = channels_for(topic, apps) + (
            ("mail",) if topic in MAIL_COLUMNS else ()
        )
        if not isinstance(channels, dict) or not channels:
            return f"{topic}: expected an object of channels"
        for channel, on in channels.items():
            if channel not in allowed:
                return f"{topic}: channels are " + ", ".join(allowed)
            if not isinstance(on, bool):
                return f"{topic}.{channel}: true or false"
    return None


def apply(member, body: dict) -> None:
    """Store a validated body; topics and channels left out keep their value."""
    stored = {t: dict(v) for t, v in (member.notify_prefs or {}).items()}
    for topic, channels in body.items():
        for channel, on in channels.items():
            if channel == "mail":
                setattr(member, MAIL_COLUMNS[topic], on)
            else:
                stored.setdefault(topic, {})[channel] = on
    # Keep only what differs from the default (bell and push off, an app on).
    kept = {
        t: {c: v for c, v in chans.items() if v is not default(c, t)}
        for t, chans in stored.items()
    }
    member.notify_prefs = {t: chans for t, chans in kept.items() if chans} or None
