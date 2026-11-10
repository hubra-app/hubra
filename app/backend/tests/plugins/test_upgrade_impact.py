"""Upgrade impact (hubra.core.plugins.impact, roadmap idea 58): installed
plugins that stop loading on another Hubra version, and the fix."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hubra.core.extensions import db as _db
from hubra.core.models.feature import Feature, TenantFeature
from hubra.core.plugins import impact

ENTRIES = [
    {
        "id": "fine",
        "name": "Fine",
        "installed": True,
        "installedVersion": "1.0.0",
        "modules": ["fine"],
        "versions": [{"version": "1.0.0", "hubra": ">=0.2"}],
    },
    {
        "id": "old",
        "name": "Old",
        "installed": True,
        "installedVersion": "1.0.0",
        "modules": ["old"],
        "versions": [
            {"version": "2.0.0", "hubra": ">=0.3", "yanked": ""},
            {"version": "1.0.0", "hubra": ">=0.2,<0.3"},
        ],
    },
    {
        "id": "stuck",
        "name": "Stuck",
        "installed": True,
        "installedVersion": "1.0.0",
        "modules": ["stuck"],
        "versions": [{"version": "1.0.0", "hubra": "<0.3"}],
    },
    {"id": "other", "name": "Not installed", "installed": False, "versions": []},
]


@pytest.fixture
def market():
    plugins = SimpleNamespace(get=lambda pid: None)
    with (
        patch(
            "hubra.core.plugins.installer.marketplace",
            lambda fetch=True: {"plugins": ENTRIES},
        ),
        patch("hubra.core.plugins.current", lambda: plugins),
    ):
        yield


def test_sorts_plugins_by_what_to_do(db, market, tenant_pair):
    tid = tenant_pair["tenant_a"].id
    _db.session.add(Feature(code="stuck", name="Stuck"))
    _db.session.flush()
    _db.session.add(TenantFeature(tenant_id=tid, feature_code="stuck", enabled=True))
    _db.session.commit()
    out = impact.check("0.3.0")
    assert out["target"] == "0.3.0"
    states = {r["id"]: (r["state"], r["updateTo"]) for r in out["plugins"]}
    assert states == {
        "stuck": ("blocked", None),
        "old": ("update", "2.0.0"),
        "fine": ("ok", None),
    }
    assert [r["id"] for r in out["plugins"]] == ["stuck", "old", "fine"]
    assert out["plugins"][0]["clubs"] == 1
    assert out["counts"] == {"ok": 1, "update": 1, "blocked": 1}


def test_bad_version_is_refused(db, market):
    with pytest.raises(impact.ImpactError):
        impact.check("next")


def test_route_answers_platform_staff(client, staff_headers, market):
    resp = client.get(
        "/api/v1/manager/plugins/upgrade-impact?version=0.3.0", headers=staff_headers
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["counts"]["blocked"] == 1
    bad = client.get(
        "/api/v1/manager/plugins/upgrade-impact?version=x", headers=staff_headers
    )
    assert bad.status_code == 400


def test_club_admin_cannot_ask(client, auth_headers, market):
    resp = client.get(
        "/api/v1/manager/plugins/upgrade-impact?version=0.3.0", headers=auth_headers
    )
    assert resp.status_code == 403


def test_no_version_means_the_next_minor(db, market):
    with patch("hubra.core.plugins.spec.hubra_version", lambda: "0.2.5"):
        assert impact.check("")["target"] == "0.3.0"
