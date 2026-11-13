"""One search across the club (docs/contracts.md, "Search").

Every module with things worth finding offers one query, named after its
module code::

    from hubra.core.contracts.search import search_contract

    provides=(search_contract("inventory", "hubra_inventory.search:hits"),)

``<module>.search`` (query): ``{"q", "limit"}`` → ``{"hits": [...]}``, at
most *limit* things the viewer may see that match *q* (every word
somewhere, case ignored). The search in the club app's top bar
(``GET /app/search``) asks every module that is on and whose right the
viewer has.
"""

from __future__ import annotations

import logging
from datetime import date as Day

from pydantic import BaseModel, Field

from .base import QUERY, Contract, query_contract

_log = logging.getLogger(__name__)

SUFFIX = ".search"
MAX_HITS = 10


class SearchIn(BaseModel):
    q: str = Field(min_length=2, max_length=100)
    limit: int = Field(default=5, ge=1, le=MAX_HITS)

    def words(self) -> list[str]:
        return self.q.split()[:5]


class SearchHit(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(max_length=300)
    sub: str | None = Field(default=None, max_length=300)
    # A day that goes with it (an event's, an invoice's); the app shows it
    # in the club's date format before ``sub``.
    date: Day | None = None
    # Where the club app opens it.
    path: str = Field(max_length=300)
    # What it is ("member", "event", ...): the badge in the result list.
    kind: str = Field(min_length=1, max_length=40)


class SearchHits(BaseModel):
    hits: list[SearchHit] = Field(default_factory=list, max_length=MAX_HITS)


def search_contract(module: str, handler: str, *, perm: str | None = None) -> Contract:
    """The search query for *module*."""
    return query_contract(
        f"{module}{SUFFIX}",
        handler,
        input=SearchIn,
        output=SearchHits,
        perm=perm,
        description="Things in this module that match a search",
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


def search(q: str, limit: int = 5) -> dict:
    """``{"hits": [...], "failed": [...]}`` for the current member, each
    hit with its ``source`` (module code), grouped by module."""
    from .base import ActionForbidden, ActionUnavailable, CallContext
    from .calls import CURRENT, _actor, _check_on, _check_perm, _run, _tenant_id

    tid = _tenant_id()
    member, system = _actor(CURRENT)
    hits: list[dict] = []
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
            result = _run(offer, {"q": q, "limit": limit}, ctx, read_only=True)
        except Exception as exc:  # noqa: BLE001 - one module must not stop the search
            _log.warning("search in %s failed: %s", module, exc)
            failed.append(module)
            continue
        hits += [
            {**hit, "source": module} for hit in (result.get("hits") or [])[:limit]
        ]
    return {"hits": hits, "failed": failed}
