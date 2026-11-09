"""What a member chooses to be notified about, as the settings pages show it.

Used by the club's own account page (``/members/me/notifications``) and by
the account page on SSO, which shows the same choices for every club.
"""

from __future__ import annotations

from hubra.core.errors import raise_error


def for_member(member) -> dict:
    """Per topic, whether the member gets it in the bell, by browser push,
    (reminders only) by mail, and through a connected app (Discord)."""
    from hubra.core.notifications import channels, prefs

    apps = channels.available(member)
    names = channels.providers()
    user = member.user if member.user_id else None
    return {
        "topics": prefs.prefs_for(member, apps),
        "apps": [{"key": code, "name": names.get(code, code)} for code in apps],
        # The weekly digest mail (hubra.core.tasks.digest_tasks), off by default;
        # also the mail column of the "digest" topic.
        "digest": bool(member.weekly_digest_mail),
        # The account's "mute all direct messages" switch (every club, and
        # the account's own messages such as sign-in alerts).
        "muted": bool(((user.dm_prefs if user else None) or {}).get("muted")),
    }


def apply(member, body) -> None:
    """Store body ``{topic: {channel: bool}}``, ``digest: bool`` for the
    weekly digest mail and ``muted: bool`` for the account's "mute all
    direct messages"; what is left out keeps its value. The caller commits."""
    from hubra.core.notifications import channels, prefs

    digest = None
    muted = None
    # "digest": true/false is the older switch; {"digest": {...}} the topic.
    if isinstance(body, dict) and "digest" in body and not isinstance(
        body["digest"], dict
    ):
        body = dict(body)
        digest = body.pop("digest")
        if not isinstance(digest, bool):
            raise_error(422, "VALIDATION_ERROR", "digest: true or false")
    if isinstance(body, dict) and "muted" in body:
        body = dict(body)
        muted = body.pop("muted")
        if not isinstance(muted, bool):
            raise_error(422, "VALIDATION_ERROR", "muted: true or false")
        if member.user_id is None:
            raise_error(422, "VALIDATION_ERROR", "muted: this member has no account")
    if body or (digest is None and muted is None):
        if err := prefs.validate(body, channels.available(member)):
            raise_error(422, "VALIDATION_ERROR", err)
        prefs.apply(member, body)
    if digest is not None:
        member.weekly_digest_mail = digest
    if muted is not None:
        from hubra.core.notifications import account_dm

        account_dm.apply(member.user, {"muted": muted})
