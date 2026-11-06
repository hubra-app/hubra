"""Notification texts in the reader's language, for pushes.

Notifications are stored in English; the apps translate the known ones with
packages/ui/src/notificationText.ts. A push has no app around it, so the
server does the same here: the same English texts, the same translation keys
(the platform's translations win), and the same German and English defaults.
tests/notifications/test_push.py checks both tables list the same texts.
"""

from __future__ import annotations

import re

# English title -> (key, German, English)
TITLES: dict[str, tuple[str, str, str]] = {
    "New post": ("shell.notif.text.newPost", "Neuer Beitrag", "New post"),
    "New event": ("shell.notif.text.newEvent", "Neuer Anlass", "New event"),
    "New poll": ("shell.notif.text.newPoll", "Neue Umfrage", "New poll"),
    "Event changed": (
        "shell.notif.text.eventChanged",
        "Anlass geändert",
        "Event changed",
    ),
    "Event reminder": (
        "shell.notif.text.eventReminder",
        "Erinnerung an einen Anlass",
        "Event reminder",
    ),
    "Event cancelled": (
        "shell.notif.text.eventCancelled",
        "Anlass abgesagt",
        "Event cancelled",
    ),
    "Sign-up to approve": (
        "shell.notif.text.signUpToApprove",
        "Anmeldung bestätigen",
        "Sign-up to approve",
    ),
    "Sign-up confirmed": (
        "shell.notif.text.signUpConfirmed",
        "Anmeldung bestätigt",
        "Sign-up confirmed",
    ),
    "Sign-up confirmed, on the waitlist": (
        "shell.notif.text.signUpWaitlist",
        "Anmeldung bestätigt, auf der Warteliste",
        "Sign-up confirmed, on the waitlist",
    ),
    "Sign-up declined": (
        "shell.notif.text.signUpDeclined",
        "Anmeldung abgelehnt",
        "Sign-up declined",
    ),
    "You got a place": (
        "shell.notif.text.gotAPlace",
        "Du hast einen Platz bekommen",
        "You got a place",
    ),
    "Request to leave": (
        "shell.notif.text.requestToLeave",
        "Austrittsgesuch",
        "Request to leave",
    ),
    "New application": (
        "shell.notif.text.newApplication",
        "Neuer Mitgliedschaftsantrag",
        "New application",
    ),
    "New device login": (
        "shell.notif.text.newDevice",
        "Anmeldung von einem neuen Gerät",
        "New device login",
    ),
    "Club limit almost reached": (
        "shell.notif.text.quotaNear",
        "Vereinslimit fast erreicht",
        "Club limit almost reached",
    ),
    "Club limit reached": (
        "shell.notif.text.quotaOver",
        "Vereinslimit erreicht",
        "Club limit reached",
    ),
    "Sign-up received": (
        "shell.notif.text.signUpReceived",
        "Anmeldung erhalten, wartet auf Bestätigung",
        "Sign-up received, waiting for approval",
    ),
    "On the waitlist": (
        "shell.notif.text.onWaitlist",
        "Auf der Warteliste",
        "On the waitlist",
    ),
    "New invoice": (
        "shell.notif.text.newInvoice",
        "Neue Rechnung",
        "New invoice",
    ),
    "Invoice due soon": (
        "shell.notif.text.invoiceDueSoon",
        "Rechnung bald fällig",
        "Invoice due soon",
    ),
    "Invoice overdue": (
        "shell.notif.text.invoiceOverdue",
        "Rechnung überfällig",
        "Invoice overdue",
    ),
    "Membership fee for the new period": (
        "shell.notif.text.membershipRenewal",
        "Mitgliederbeitrag für die neue Periode",
        "Membership fee for the new period",
    ),
    "Qualification ends soon": (
        "shell.notif.text.qualificationEnds",
        "Qualifikation läuft bald ab",
        "Qualification ends soon",
    ),
    "Your week": (
        "shell.notif.text.weeklyDigest",
        "Deine Woche im Verein",
        "Your week at the club",
    ),
}

# English prefix -> (key, German, English); {{subject}} is the rest.
PREFIXES: tuple[tuple[str, str, str, str], ...] = (
    (
        "New vote: ",
        "shell.notif.text.newVote",
        "Neue Stimme: {{subject}}",
        "New vote: {{subject}}",
    ),
    (
        "Reminder: ",
        "shell.notif.text.reminder",
        "Erinnerung: {{subject}}",
        "Reminder: {{subject}}",
    ),
    (
        "Proxy vote: ",
        "shell.notif.text.proxyVote",
        "Vertretung: {{subject}}",
        "Proxy vote: {{subject}}",
    ),
)

# English message pattern -> (key, German, English); named groups fill in.
MESSAGES: tuple[tuple[re.Pattern, str, str, str], ...] = (
    (
        re.compile(
            r"^Your account was accessed from a new device or location at (?P<time>.+?)\. "
        ),
        "shell.notif.text.newDeviceMsg",
        "Dein Konto wurde am {{time}} von einem neuen Gerät oder Ort aus benutzt. "
        "Warst du das nicht, beende die Sitzung im Konto unter Sitzungen.",
        "Your account was used from a new device or location at {{time}}. "
        "If this wasn't you, end the session under Account › Sessions.",
    ),
    (
        re.compile(r"^Please cast your vote before the poll closes\.$"),
        "shell.notif.text.castVote",
        "Bitte stimme ab, bevor die Umfrage schliesst.",
        "Please cast your vote before the poll closes.",
    ),
    (
        re.compile(r"^(?P<name>.+) voted for (?P<option>.+)$"),
        "shell.notif.text.votedFor",
        "{{name}} hat für «{{option}}» gestimmt",
        '{{name}} voted for "{{option}}"',
    ),
    (
        re.compile(r"^(?P<name>.+) asked you to vote for them\.$"),
        "shell.notif.text.askedProxy",
        "{{name}} hat dir die Stimme übertragen.",
        "{{name}} asked you to vote for them.",
    ),
    (
        re.compile(r"^Members: (?P<used>\d+) of (?P<limit>\d+)\.$"),
        "shell.notif.text.quotaMembers",
        "Mitglieder: {{used}} von {{limit}}.",
        "Members: {{used}} of {{limit}}.",
    ),
    (
        re.compile(r"^Mails this month: (?P<used>\d+) of (?P<limit>\d+)\.$"),
        "shell.notif.text.quotaMail",
        "Mails diesen Monat: {{used}} von {{limit}}.",
        "Mails this month: {{used}} of {{limit}}.",
    ),
    (
        re.compile(r"^Storage: (?P<used>\d+) MB of (?P<limit>\d+) MB\.$"),
        "shell.notif.text.quotaStorage",
        "Speicher: {{used}} MB von {{limit}} MB.",
        "Storage: {{used}} MB of {{limit}} MB.",
    ),
)

_CHAIN = {"en-GB": ("en-GB",), "de-CH": ("de-CH", "en-GB")}


def _fill(text: str, values: dict[str, str]) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m[1], m[0]), text)


def _lookup(key: str, locale: str) -> str | None:
    """The platform's translation of *key*, if it has one."""
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.translation import Translation

    chain = _CHAIN.get(locale, ("de-CH", "en-GB"))
    rows = dict(
        db.session.execute(
            select(Translation.locale, Translation.value).where(
                Translation.key == key, Translation.locale.in_(chain)
            )
        ).all()
    )
    for loc in chain:
        if rows.get(loc):
            return rows[loc]
    return None


def _text(key: str, de: str, en: str, locale: str, values: dict[str, str]) -> str:
    default = en if locale.lower().startswith("en") else de
    return _fill(_lookup(key, locale) or default, values)


def translate(title: str, msg: str, locale: str) -> tuple[str, str]:
    """(title, message) in *locale*; unknown texts stay as they are."""
    heading = title
    if title in TITLES:
        heading = _text(*TITLES[title], locale, {})
    else:
        for prefix, key, de, en in PREFIXES:
            if title.startswith(prefix):
                heading = _text(key, de, en, locale, {"subject": title[len(prefix) :]})
                break
    body = msg
    for pattern, key, de, en in MESSAGES:
        if m := pattern.match(msg or ""):
            body = _text(key, de, en, locale, m.groupdict())
            break
    return heading, body


def safe_link(link: str | None) -> str | None:
    """Only paths inside the club app (as safeNotificationLink)."""
    return link if link and re.match(r"^/app/[^/]", link) else None
