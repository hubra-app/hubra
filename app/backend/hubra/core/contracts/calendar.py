"""One club calendar (docs/contracts.md, "Calendar").

Every module with dated things (events in core, bookings, fixtures, board
duties) offers one query, named after its module code::

    from hubra.core.contracts.calendar import calendar_contract

    provides=(
        calendar_contract(
            "booking",
            "hubra_booking.calendar:items",
            perm="booking.bookings.read",
        ),
    )

``<module>.calendar.items`` (query): ``{"start", "end"}`` (dates, both
included) → ``{"items": [...]}``, the module's items in that range that the
viewer may see. Times are the club's local time, without a zone. The club
calendar (``GET /app/calendar``) asks every module that is on and whose
right the viewer has, and puts the answers side by side.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from .base import QUERY, Contract, query_contract

_log = logging.getLogger(__name__)

SUFFIX = ".calendar.items"
# What one module may answer for one range.
MAX_ITEMS = 1000
# The widest range a viewer can ask for (a year and a bit).
MAX_DAYS = 400


class CalendarRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _order(self):
        if self.end < self.start:
            raise ValueError("end before start")
        return self


class CalendarItem(BaseModel):
    # Unique within the module, e.g. "event:12".
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(max_length=300)
    # What it is, for the filter and the colour: "event", "booking", ...
    kind: str = Field(min_length=1, max_length=40)
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = Field(default=None, max_length=300)
    # Where the club app opens it, e.g. "/app/operations/events?event=12".
    path: str | None = Field(default=None, max_length=300)
    group_id: int | None = None
    color: str | None = Field(default=None, max_length=20)
    cancelled: bool = False


class CalendarItems(BaseModel):
    items: list[CalendarItem] = Field(default_factory=list, max_length=MAX_ITEMS)


def calendar_contract(
    module: str, handler: str, *, perm: str | None = None
) -> Contract:
    """The calendar query for *module*."""
    return query_contract(
        f"{module}{SUFFIX}",
        handler,
        input=CalendarRange,
        output=CalendarItems,
        perm=perm,
        description="Dated items for the club calendar",
    )


def _offered() -> list:
    from .registry import offers

    return sorted(
        (
            o
            for name, o in offers().items()
            if o.contract.kind == QUERY and name.endswith(SUFFIX)
        ),
        key=lambda o: o.contract.name,
    )


def items(start: date, end: date) -> dict:
    """``{"items": [...], "sources": [...]}`` for the current member: every
    module's items in the range, each with its ``source`` (module code).
    A module that is off or whose right the member lacks is left out; one
    that fails is listed under ``failed`` instead of failing the calendar."""
    from .calls import CURRENT, _actor, _check_on, _check_perm, _run, _tenant_id
    from .base import ActionForbidden, ActionUnavailable, CallContext

    tid = _tenant_id()
    member, system = _actor(CURRENT)
    out: list[dict] = []
    sources: list[str] = []
    failed: list[str] = []
    for offer in _offered():
        module = offer.contract.name[: -len(SUFFIX)]
        try:
            _check_on(offer, tid)
            _check_perm(offer, member, system)
        except (ActionUnavailable, ActionForbidden):
            continue
        ctx = CallContext(tid, offer.contract.name, "core", actor=member, system=system)
        try:
            result = _run(
                offer,
                {"start": start.isoformat(), "end": end.isoformat()},
                ctx,
                read_only=True,
            )
        except Exception as exc:  # noqa: BLE001 - one module must not stop the calendar
            _log.warning("calendar items of %s failed: %s", module, exc)
            failed.append(module)
            continue
        sources.append(module)
        out += [{**item, "source": module} for item in result.get("items") or []]
    out.sort(key=lambda i: (i["start"], i["title"]))
    return {"items": out, "sources": sources, "failed": failed}
