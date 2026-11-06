"""Dashboard widgets that modules and plugins offer as contracts
(docs/contracts.md, docs/dashboards.md)."""

from __future__ import annotations

import pytest

from hubra.core.contracts.base import WidgetField, widget_contract
from hubra.core.modules import Module, registry
from tests.authz.conftest import (  # noqa: F401
    _login_member,
    permissioned_member_factory,
    plain_member_token,
)

HERE = __name__
URL = "/api/v1/app/dashboards/widgets"


def lent_count(ctx, config):
    return {"value": 3 * config["factor"], "sub": "lent out", "path": "/app/demo"}


def lent_list(ctx, config):
    return {
        "items": [{"label": f"Drill {i}"} for i in range(config["count"])],
        "total": 9,
    }


def broken(ctx, config):
    return {"no": "value"}


DEMO = Module(
    code="demo",
    name="Demo",
    plugin="demo",
    provides=(
        widget_contract(
            "demo.lent",
            f"{HERE}:lent_count",
            label="Lent out",
            size="s",
            view="stat",
            fields=(WidgetField("factor", "Factor", "number", 1),),
        ),
        widget_contract(
            "demo.lent_list",
            f"{HERE}:lent_list",
            label="Lent items",
            view="list",
            perm="demo.items.read",
            fields=(WidgetField("count", "How many", "number", 2),),
        ),
        widget_contract("demo.broken", f"{HERE}:broken", label="Broken", view="stat"),
    ),
)


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setitem(registry._modules, "demo", DEMO)
    on = {"demo": True}
    real = __import__("hubra.core.modules.state", fromlist=["is_enabled"]).is_enabled

    def is_enabled(code, tenant_id=None):
        return on[code] if code in on else real(code, tenant_id=tenant_id)

    monkeypatch.setattr("hubra.core.modules.state.is_enabled", is_enabled)
    return on


def test_members_see_the_widgets_their_rights_allow(client, plain_member_token, demo):  # noqa: F811
    resp = client.get(URL, headers=plain_member_token)
    assert resp.status_code == 200
    items = {w["name"]: w for w in resp.get_json()["items"]}
    assert set(items) == {"demo.lent", "demo.broken"}  # no demo.items.read
    lent = items["demo.lent"]
    assert (
        lent["type"] == "w:demo.lent" and lent["size"] == "s" and lent["view"] == "stat"
    )
    assert lent["fields"] == [
        {"key": "factor", "label": "Factor", "kind": "number", "default": 1}
    ]
    assert lent["plugin"] == "demo"


def test_widget_data_is_read_as_the_member(client, plain_member_token, demo):  # noqa: F811
    resp = client.post(
        f"{URL}/demo.lent/data",
        json={"config": {"factor": "2"}},
        headers=plain_member_token,
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["data"] == {
        "value": 6,
        "sub": "lent out",
        "path": "/app/demo",
    }
    # A right the member lacks.
    resp = client.post(
        f"{URL}/demo.lent_list/data", json={}, headers=plain_member_token
    )
    assert resp.status_code == 403


def test_admins_get_list_widgets(client, auth_headers, demo):
    _login_member(client, "admin@test.ch")
    resp = client.post(
        f"{URL}/demo.lent_list/data",
        json={"config": {"count": 2}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"] == {
        "items": [
            {"label": "Drill 0", "sub": None, "path": None},
            {"label": "Drill 1", "sub": None, "path": None},
        ],
        "total": 9,
    }


def test_off_unknown_and_broken_widgets(client, plain_member_token, demo):  # noqa: F811
    assert (
        client.post(
            f"{URL}/demo.broken/data", json={}, headers=plain_member_token
        ).status_code
        == 502
    )
    assert (
        client.post(
            f"{URL}/nope.nothing/data", json={}, headers=plain_member_token
        ).status_code
        == 404
    )
    demo["demo"] = False
    assert (
        client.post(
            f"{URL}/demo.lent/data", json={}, headers=plain_member_token
        ).status_code
        == 404
    )
    assert client.get(URL, headers=plain_member_token).get_json()["items"] == []


def test_widget_contracts_are_checked(tmp_path):
    from hubra.core.plugins.limits import LimitError, check
    from hubra.core.plugins.spec import Spec

    with pytest.raises(ValueError, match="size"):
        widget_contract("demo.x", f"{HERE}:broken", label="X", size="xl")
    with pytest.raises(ValueError, match="view"):
        widget_contract("demo.x", f"{HERE}:broken", label="X", view="chart")
    spec = Spec(
        id="demo",
        path=tmp_path,
        manifest={"id": "demo", "name": "D", "version": "1", "package": "hubra_demo"},
        trust={"status": "community", "signer": "", "key_id": "", "detail": ""},
    )
    bad = Module(
        code="demo",
        name="D",
        provides=(widget_contract("other.x", "hubra_demo.w:x", label="X"),),
    )
    with pytest.raises(LimitError, match="named"):
        check(bad, spec, {}, set())
    ok = Module(
        code="demo",
        name="D",
        provides=(widget_contract("demo.x", "hubra_demo.w:x", label="X"),),
    )
    assert check(ok, spec, {}, set())
