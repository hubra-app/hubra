"""Attendance per event date, and the overview per group and per member.

An organiser or trainer takes the roll of one event: who was ``present``,
``excused`` or ``absent``. Expected at an event are the members of its group
(those who had joined the group by then), whoever holds a place, and anyone
the roll lists. The overview counts, per member, the dates they were
expected at and those they came to.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.api.utils import csv_safe
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventAttendance, EventRegistration
from hubra.core.models.group import GroupMembership
from hubra.core.models.member import Member, member_groups

STATUSES = ("present", "excused", "absent")
# Sign-ups that make a member expected at the event.
_SIGNED_UP = ("registered", "approved", "attended")


def _group_members(group_ids: set[int]) -> dict[int, dict[int, date | None]]:
    """Per group, its members and the day each joined (``None`` when not
    known: they count from the start)."""
    out: dict[int, dict[int, date | None]] = {g: {} for g in group_ids}
    if not group_ids:
        return out
    for group_id, member_id in db.session.execute(
        select(member_groups.c.group_id, member_groups.c.member_id).where(
            member_groups.c.group_id.in_(group_ids)
        )
    ).all():
        out[group_id][member_id] = None
    for gm in db.session.scalars(
        select(GroupMembership).where(GroupMembership.group_id.in_(group_ids))
    ).all():
        if gm.member_id in out[gm.group_id] and gm.joined_at:
            out[gm.group_id][gm.member_id] = gm.joined_at.date()
    return out


def _grid(events: list[ClubEvent]):
    """Who was expected at each event and what was recorded.

    Returns ``(expected, recorded, signed_up)``: per event id the set of
    expected member ids, ``{member_id: status}`` and the sign-up status.
    """
    ids = [e.id for e in events]
    recorded: dict[int, dict[int, str]] = {i: {} for i in ids}
    signed_up: dict[int, dict[int, str]] = {i: {} for i in ids}
    if ids:
        for a in db.session.scalars(
            select(EventAttendance).where(EventAttendance.event_id.in_(ids))
        ).all():
            recorded[a.event_id][a.member_id] = a.status
        for r in db.session.scalars(
            select(EventRegistration).where(
                EventRegistration.event_id.in_(ids),
                EventRegistration.status != "cancelled",
            )
        ).all():
            signed_up[r.event_id][r.member_id] = r.status
    groups = _group_members({e.group_id for e in events if e.group_id})
    expected: dict[int, set[int]] = {}
    for e in events:
        who = {
            m
            for m, joined in groups.get(e.group_id, {}).items()
            if joined is None or joined <= e.date
        }
        who |= {m for m, s in signed_up[e.id].items() if s in _SIGNED_UP}
        who |= set(recorded[e.id])
        expected[e.id] = who
    return expected, recorded, signed_up


def _members(ids) -> dict[int, Member]:
    if not ids:
        return {}
    return {
        m.id: m
        for m in db.session.scalars(
            select(Member)
            .where(Member.id.in_(ids))
            .options(selectinload(Member.user))
        ).all()
    }


def roll(event: ClubEvent) -> list[dict]:
    """The roll of one event: everyone expected, by name, with their sign-up
    and what was recorded (``None`` when nothing yet)."""
    expected, recorded, signed_up = _grid([event])
    members = _members(expected[event.id])
    rows = [
        {
            "member_id": m.id,
            "member_name": m.name,
            "registration_status": signed_up[event.id].get(m.id),
            "status": recorded[event.id].get(m.id),
        }
        for m in members.values()
        if m.archived_at is None or m.id in recorded[event.id]
    ]
    rows.sort(key=lambda r: (r["member_name"] or "").lower())
    return rows


def set_status(event: ClubEvent, member_id: int, status: str | None, actor_id: int):
    """Record one member's attendance (``None`` clears it).

    A sign-up follows along: present marks it attended, and taking that back
    returns it to a place.
    """
    if status is not None and status not in STATUSES:
        raise_error(400, "VALIDATION_ERROR", f"Unknown status {status!r}")
    member = db.session.get(Member, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
    row = db.session.scalar(
        select(EventAttendance).where(
            EventAttendance.event_id == event.id,
            EventAttendance.member_id == member_id,
        )
    )
    if status is None:
        if row is not None:
            db.session.delete(row)
    else:
        if row is None:
            row = EventAttendance(event_id=event.id, member_id=member_id, status=status)
            db.session.add(row)
        row.status = status
        row.marked_by = actor_id
        row.marked_at = datetime.now(timezone.utc)

    reg = db.session.scalar(
        select(EventRegistration).where(
            EventRegistration.event_id == event.id,
            EventRegistration.member_id == member_id,
        )
    )
    if reg is not None:
        if status == "present" and reg.status in ("registered", "approved"):
            reg.status = "attended"
            reg.attended_at = datetime.now(timezone.utc)
        elif status != "present" and reg.status == "attended":
            reg.status = "approved" if event.requires_approval else "registered"
            reg.attended_at = None
    return row


def save_roll(event: ClubEvent, entries: list[dict], actor_id: int) -> None:
    """Record several members at once (``[{member_id, status}]``)."""
    for entry in entries:
        set_status(event, entry["member_id"], entry.get("status"), actor_id)
    db.session.flush()


# ── Overview ──────────────────────────────────────────────────────────────────


def _events(
    since: date,
    until: date,
    group_id: int | None = None,
    series_id: int | None = None,
    category: str = "",
    type_: str = "",
) -> list[ClubEvent]:
    query = (
        select(ClubEvent)
        .where(ClubEvent.date >= since, ClubEvent.date <= until)
        .order_by(ClubEvent.date, ClubEvent.time, ClubEvent.id)
    )
    if group_id is not None:
        query = query.where(ClubEvent.group_id == group_id)
    if series_id is not None:
        query = query.where(ClubEvent.series_id == series_id)
    if category:
        query = query.where(ClubEvent.category == category)
    if type_:
        query = query.where(ClubEvent.type == type_)
    return list(db.session.scalars(query).all())


def _summary(present: int, excused: int, expected: int) -> dict:
    return {
        "present": present,
        "excused": excused,
        "absent": expected - present - excused,
        "expected": expected,
        "rate": round(present / expected, 3) if expected else None,
    }


def overview(since: date, until: date, **filters) -> dict:
    """Attendance of every expected member over the matching events.

    ``{"events": [...], "members": [{member_id, name, birthday, statuses:
    {event_id: status}, ...summary}], "total": summary}``. A status is
    ``present``, ``excused``, or ``absent`` (expected, nothing recorded or
    marked absent); events a member was not expected at are left out.
    """
    if until < since:
        raise_error(400, "VALIDATION_ERROR", "'to' is before 'from'")
    events = _events(since, until, **filters)
    expected, recorded, _ = _grid(events)
    member_ids = set().union(*expected.values()) if expected else set()
    members = _members(member_ids)
    rows = []
    totals = [0, 0, 0]
    for mid, m in members.items():
        if m.archived_at is not None and not any(mid in recorded[e.id] for e in events):
            continue  # left the club; only what was recorded about them counts
        statuses = {}
        for e in events:
            if mid in expected[e.id]:
                statuses[e.id] = recorded[e.id].get(mid) or "absent"
        present = sum(1 for s in statuses.values() if s == "present")
        excused = sum(1 for s in statuses.values() if s == "excused")
        totals[0] += present
        totals[1] += excused
        totals[2] += len(statuses)
        rows.append(
            {
                "member_id": mid,
                "first_name": m.first_name,
                "last_name": m.last_name,
                "name": m.name,
                "birthday": m.birthday.isoformat() if m.birthday else None,
                "statuses": {str(k): v for k, v in statuses.items()},
                **_summary(present, excused, len(statuses)),
            }
        )
    rows.sort(key=lambda r: ((r["last_name"] or "").lower(), (r["first_name"] or "").lower()))
    return {
        "from": since.isoformat(),
        "to": until.isoformat(),
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "date": e.date.isoformat(),
                "time": e.time,
                "group_id": e.group_id,
                "series_id": e.series_id,
                "recorded": bool(recorded[e.id]),
                "present": sum(1 for s in recorded[e.id].values() if s == "present"),
            }
            for e in events
        ],
        "members": rows,
        "total": _summary(*totals),
    }


def member_history(member_id: int, since: date, until: date) -> dict:
    """One member's dates in the period: those they were expected at, with
    what was recorded, and the summary."""
    events = _events(since, until)
    expected, recorded, _ = _grid(events)
    dates = []
    for e in events:
        if member_id in expected[e.id]:
            dates.append(
                {
                    "event_id": e.id,
                    "title": e.title,
                    "date": e.date.isoformat(),
                    "time": e.time,
                    "group_id": e.group_id,
                    "status": recorded[e.id].get(member_id) or "absent",
                }
            )
    present = sum(1 for d in dates if d["status"] == "present")
    excused = sum(1 for d in dates if d["status"] == "excused")
    return {
        "member_id": member_id,
        "from": since.isoformat(),
        "to": until.isoformat(),
        "events": dates,
        **_summary(present, excused, len(dates)),
    }


_CELL = {"present": "1", "excused": "E", "absent": "0"}


def overview_csv(data: dict, with_birthday: bool) -> str:
    """The overview as a sheet: a row per member, a column per date
    (1 present, E excused, 0 absent, empty when not expected), then the
    sums. Semicolons and a byte order mark for Swiss Excel, as the member
    export."""
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";")
    events = data["events"]
    days = [e["date"] for e in events]
    heads = []
    for e in events:
        y, mo, d = e["date"].split("-")
        head = f"{d}.{mo}.{y}"
        if days.count(e["date"]) > 1:
            head = f"{head} {e['time'] or e['title']}"
        heads.append(head)
    first = ["Nachname", "Vorname"] + (["Geburtsdatum"] if with_birthday else [])
    writer.writerow(
        first + heads + ["Anwesend", "Entschuldigt", "Abwesend", "Erwartet", "Quote %"]
    )
    for row in data["members"]:
        cells = [row["last_name"], row["first_name"]]
        if with_birthday:
            bd = row["birthday"]
            cells.append(".".join(reversed(bd.split("-"))) if bd else "")
        cells += [_CELL.get(row["statuses"].get(str(e["id"])), "") for e in events]
        rate = "" if row["rate"] is None else f"{row['rate'] * 100:.0f}"
        cells += [row["present"], row["excused"], row["absent"], row["expected"], rate]
        writer.writerow([csv_safe(c) for c in cells])
    return out.getvalue()
