"""Which notifications a member wants, per topic and channel.

Each notification belongs to a topic (new posts, reminders, my sign-ups...).
Per topic a member turns the bell (in Hubra) and browser push on or off, and
mail where Hubra mails that topic (the reminders).  Everything is on until the
member turns it off.  A notification without a topic (a sign-in from a new
device, a notice to the club's owners) always comes.

Bell and push are stored in ``members.notify_prefs``; the reminder mails keep
their own columns (``event_reminder_mail``, ``poll_reminder_mail``).
"""

from __future__ import annotations

TOPICS = (
    "posts",
    "events",
    "polls",
    "event_reminders",
    "poll_reminders",
    "my_events",
    "my_polls",
    "tasks",
)
CHANNELS = ("bell", "push")
# Topics that also go by mail, and the member column that switches it.
MAIL_COLUMNS = {
    "event_reminders": "event_reminder_mail",
    "poll_reminders": "poll_reminder_mail",
}


def wants(stored: dict | None, topic: str | None, channel: str) -> bool:
    """Whether a member with ``notify_prefs`` *stored* gets *topic* on
    *channel*.  No topic: always."""
    if not topic:
        return True
    value = ((stored or {}).get(topic) or {}).get(channel, True)
    return value is not False


def prefs_for(member) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for topic in TOPICS:
        row = {c: wants(member.notify_prefs, topic, c) for c in CHANNELS}
        if topic in MAIL_COLUMNS:
            row["mail"] = bool(getattr(member, MAIL_COLUMNS[topic]))
        out[topic] = row
    return out


def validate(body) -> str | None:
    """Error text for a body of ``{topic: {channel: bool}}``, or None."""
    if not isinstance(body, dict) or not body:
        return "Expected an object of topics"
    for topic, channels in body.items():
        if topic not in TOPICS:
            return f"Unknown topic: {topic}"
        allowed = CHANNELS + (("mail",) if topic in MAIL_COLUMNS else ())
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
    # Keep only what is off: on is the default.
    member.notify_prefs = {
        t: {c: v for c, v in chans.items() if v is False}
        for t, chans in stored.items()
        if any(v is False for v in chans.values())
    } or None
