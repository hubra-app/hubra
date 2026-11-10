"""Modules' own data in the privacy export and the deletion
(hubra/core/contracts/privacy.py)."""

# ruff: noqa: F811 - pytest fixtures imported from the data request tests

from __future__ import annotations

import pytest

from hubra.core.contracts.base import Refused
from hubra.core.contracts.privacy import privacy_contracts
from hubra.core.models.member import Member
from hubra.core.modules import Module, registry
from tests.manager.test_data_requests import _create, anna, club  # noqa: F401

HERE = __name__
ERASED: list[int] = []
FAIL = {"erase": False}


def export_handler(ctx, data):
    return {"data": {"nickname": f"member {data.member_id}", "system": ctx.system}}


def erase_handler(ctx, data):
    if FAIL["erase"]:
        raise Refused("NOT_NOW", "The other service is down")
    ERASED.append(data.member_id)
    return {"rows": 2}


DEMO = Module(
    code="demo",
    name="Demo",
    plugin="demo",
    provides=privacy_contracts(
        "demo", export=f"{HERE}:export_handler", erase=f"{HERE}:erase_handler"
    ),
)


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setitem(registry._modules, "demo", DEMO)
    ERASED.clear()
    FAIL["erase"] = False
    # Off for the club: its data still counts.
    real = __import__("hubra.core.modules.state", fromlist=["is_enabled"]).is_enabled
    monkeypatch.setattr(
        "hubra.core.modules.state.is_enabled",
        lambda code, tenant_id=None: (
            False if code == "demo" else real(code, tenant_id=tenant_id)
        ),
    )
    return DEMO


def test_the_export_has_what_modules_keep(client, staff_headers, club, anna, demo):  # noqa: F811
    req = _create(client, club, kind="export", member_id=anna.id)
    resp = client.post(f"/api/v1/system/data-requests/{req['id']}/export")
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["modules"]["demo"] == {
        "nickname": f"member {anna.id}",
        "system": True,
    }


def test_the_deletion_erases_what_modules_keep(
    client,
    staff_headers,
    db,
    club,
    anna,
    demo,  # noqa: F811
):
    member_id = anna.id
    req = _create(client, club, kind="deletion", member_id=member_id)
    resp = client.post(
        f"/api/v1/system/data-requests/{req['id']}/delete-member",
        json={"confirm": "club-a"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert ERASED == [member_id]


def test_a_module_that_cannot_erase_stops_the_deletion(
    client,
    staff_headers,
    db,
    club,
    anna,
    demo,  # noqa: F811
):
    FAIL["erase"] = True
    member_id = anna.id
    req = _create(client, club, kind="deletion", member_id=member_id)
    resp = client.post(
        f"/api/v1/system/data-requests/{req['id']}/delete-member",
        json={"confirm": "club-a"},
    )
    assert resp.status_code == 409
    assert "PRIVACY_ERASE_FAILED" in resp.get_data(as_text=True), resp.get_json()
    db.session.expire_all()
    assert db.session.get(Member, member_id) is not None
