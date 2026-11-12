"""Personal data a module keeps, in the privacy export and the deletion
(revDSG; docs/contracts.md, "Privacy").

Core already exports and deletes every club row that points at a member
with a foreign key. A module that keeps more (rows found by email or
account, files, data in another service) offers two contracts, named
after its module code::

    from hubra.core.contracts.privacy import privacy_contracts

    provides=(
        *privacy_contracts(
            "documents",
            export="hubra_documents.privacy:export",
            erase="hubra_documents.privacy:erase",
        ),
    )

- ``<module>.privacy.export`` (query): ``{"member_id"}`` →
  ``{"data": {...}}``, plain JSON of what the module keeps about the
  member beyond its foreign-key rows. It lands in the export under
  ``modules.<module>``.
- ``<module>.privacy.erase`` (action): ``{"member_id"}`` →
  ``{"rows": n}``. Delete or anonymise that data. It runs inside the
  member's deletion, before core removes the member; if it fails, the
  deletion stops and nothing is deleted.

Both run as the system, also for a module the club has switched off: the
data is still there, and the promise holds either way.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from hubra.core.extensions import db

from .base import ACTION, QUERY, CallContext, Contract, action_contract, query_contract

_log = logging.getLogger(__name__)

EXPORT = ".privacy.export"
ERASE = ".privacy.erase"


class PrivacyMember(BaseModel):
    member_id: int


class PrivacyExport(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class PrivacyErased(BaseModel):
    rows: int = 0


def privacy_contracts(
    module: str, *, export: str, erase: str
) -> tuple[Contract, Contract]:
    """The export query and the erase action for *module*."""
    return (
        query_contract(
            f"{module}{EXPORT}",
            export,
            input=PrivacyMember,
            output=PrivacyExport,
            description="What the module keeps about a member, for the privacy export",
        ),
        action_contract(
            f"{module}{ERASE}",
            erase,
            input=PrivacyMember,
            output=PrivacyErased,
            description="Delete what the module keeps about a member",
        ),
    )


def _offered(suffix: str, kind: str) -> list:
    from .registry import offers

    return sorted(
        (
            o
            for name, o in offers().items()
            if o.contract.kind == kind and name.endswith(suffix)
        ),
        key=lambda o: o.contract.name,
    )


def _module(offer, suffix: str) -> str:
    return offer.contract.name[: -len(suffix)]


def _tenant_id():
    from .calls import _tenant_id as tid

    return tid()


def export(member_id: int) -> dict[str, dict]:
    """``{module: data}`` from every module that offers an export. A module
    that fails is listed with an ``error`` instead of failing the export."""
    from .calls import _run

    out: dict[str, dict] = {}
    for offer in _offered(EXPORT, QUERY):
        module = _module(offer, EXPORT)
        ctx = CallContext(_tenant_id(), offer.contract.name, "core", system=True)
        try:
            result = _run(offer, {"member_id": member_id}, ctx, read_only=True)
        except Exception as exc:  # noqa: BLE001 - one module must not stop the export
            _log.warning("privacy export of %s failed: %s", module, exc)
            out[module] = {"error": "This module's data could not be read"}
            continue
        if result.get("data"):
            out[module] = result["data"]
    return out


class EraseFailed(RuntimeError):
    """A module could not delete its data; the deletion must stop."""

    def __init__(self, module: str):
        super().__init__(f"{module} could not delete the member's data")
        self.module = module


def erase(member_id: int) -> dict[str, int]:
    """Run every module's erase for *member_id*, in this transaction.
    ``{module: rows}``. Raises EraseFailed on the first module that fails."""
    from .calls import _run

    done: dict[str, int] = {}
    for offer in _offered(ERASE, ACTION):
        module = _module(offer, ERASE)
        ctx = CallContext(_tenant_id(), offer.contract.name, "core", system=True)
        try:
            result = _run(offer, {"member_id": member_id}, ctx, read_only=False)
        except Exception as exc:  # noqa: BLE001 - any failure stops the deletion
            _log.error("privacy erase of %s failed: %s", module, exc)
            raise EraseFailed(module) from exc
        done[module] = int(result.get("rows") or 0)
    db.session.flush()
    return done
