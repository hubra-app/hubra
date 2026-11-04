"""Unexpected API errors grouped by route and build: manage › Diagnose › Fehler."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import got_request_exception

from hubra.core.models.error_group import ErrorGroup
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.services import error_tracker

BASE = "/api/v1/manager/platform/errors"


def _boom(kind: str = "label"):
    """An exception raised in Hubra's own code (error_tracker.py)."""
    try:
        if kind == "label":
            error_tracker.build_label("1.0", 12345)  # int has no [:7]
        else:
            error_tracker._scrub(None)
    except TypeError as exc:
        return exc
    raise AssertionError("no exception")


@pytest.fixture
def build():
    """Pretend the running build is *version* / *commit*."""

    def set_build(version, commit):
        patches = [
            patch.object(error_tracker.build_info, "version", return_value=version),
            patch.object(error_tracker.build_info, "commit", return_value=commit),
        ]
        for p in patches:
            p.start()
        started.extend(patches)

    started: list = []
    set_build("1.4.0", "a" * 40)
    yield set_build
    for p in reversed(started):  # the newest first, or the mocks stay
        p.stop()


def _groups(db):
    db.session.expire_all()
    return db.session.query(ErrorGroup).order_by(ErrorGroup.id).all()


def test_same_error_is_one_group_counted_per_build(db, build):
    error_tracker.capture(_boom(), route="GET /api/v1/members")
    error_tracker.capture(_boom(), route="GET /api/v1/members")
    build("1.5.0", "b" * 40)
    error_tracker.capture(_boom(), route="GET /api/v1/members")

    (g,) = _groups(db)
    assert g.count == 3
    assert g.exc_type == "TypeError"
    assert g.location == "hubra/core/services/error_tracker.py in build_label"
    assert g.first_version == "1.4.0" and g.last_version == "1.5.0"
    assert g.builds == {"1.4.0 (aaaaaaa)": 2, "1.5.0 (bbbbbbb)": 1}
    assert "error_tracker.py" in g.traceback

    kinds = [e.kind for e in db.session.query(PlatformEvent).all()]
    assert kinds == ["error.new"]  # only the first one is news


def test_other_route_or_place_is_another_group(db, build):
    error_tracker.capture(_boom(), route="GET /api/v1/members")
    error_tracker.capture(_boom(), route="GET /api/v1/events")
    error_tracker.capture(_boom("scrub"), route="GET /api/v1/members")
    assert len(_groups(db)) == 3


def test_email_addresses_are_masked(db, build):
    error_tracker.capture(ValueError("no account for anna@example.ch"), route="X")
    (g,) = _groups(db)
    assert g.message == "no account for <email>"
    assert "anna@" not in g.traceback


def test_capture_never_raises(db):
    with patch.object(error_tracker, "_capture", side_effect=RuntimeError("db down")):
        error_tracker.capture(_boom(), route="X")  # no exception


def test_request_exception_is_captured_with_its_route(app, db, build):
    with app.test_request_context("/api/v1/app/members", method="POST"):
        got_request_exception.send(app, exception=_boom())
    (g,) = _groups(db)
    assert g.route == "POST /api/v1/app/members/"  # the rule, not the path


def test_list_detail_resolve_and_regression(client, db, staff_headers, build):
    error_tracker.capture(_boom(), route="GET /api/v1/members")
    error_tracker.capture(_boom("scrub"), route="GET /api/v1/events")
    for _ in range(3):
        error_tracker.capture(_boom("scrub"), route="GET /api/v1/events")

    body = client.get(BASE).get_json()
    assert body["counts"] == {"open": 2, "resolved": 0}
    assert body["current_build"] == "1.4.0 (aaaaaaa)"
    assert body["builds"] == {"1.4.0 (aaaaaaa)": 5}
    assert [e["route"] for e in body["errors"]][0] in (
        "GET /api/v1/members",
        "GET /api/v1/events",
    )
    assert all(e["new_in_current"] for e in body["errors"])

    by_count = client.get(f"{BASE}?sort=count").get_json()["errors"]
    assert by_count[0]["count"] == 4
    found = client.get(f"{BASE}?q=events").get_json()["errors"]
    assert [e["route"] for e in found] == ["GET /api/v1/events"]

    gid = by_count[0]["id"]
    detail = client.get(f"{BASE}/{gid}").get_json()["error"]
    assert "traceback" in detail and detail["first_build"] == "1.4.0 (aaaaaaa)"

    resp = client.post(f"{BASE}/{gid}/resolve")
    assert resp.status_code == 200, resp.get_json()
    assert client.get(BASE).get_json()["counts"] == {"open": 1, "resolved": 1}
    assert len(client.get(f"{BASE}?status=resolved").get_json()["errors"]) == 1

    # It happens again on a newer build: open again, and news again.
    build("1.5.0", "b" * 40)
    error_tracker.capture(_boom("scrub"), route="GET /api/v1/events")
    (again,) = [g for g in _groups(db) if g.id == gid]
    assert again.status == "open" and again.reopened_at is not None
    kinds = [e.kind for e in db.session.query(PlatformEvent).all()]
    assert "error.regressed" in kinds
    listed = client.get(BASE).get_json()
    assert listed["counts"] == {"open": 2, "resolved": 0}
    # First seen on 1.4.0, so not new in 1.5.0.
    assert not any(e["new_in_current"] for e in listed["errors"])
    only_new = client.get(f"{BASE}?build=1.5.0 (bbbbbbb)").get_json()["errors"]
    assert [e["id"] for e in only_new] == [gid]


def test_bad_filters_and_missing_group(client, staff_headers):
    assert client.get(f"{BASE}?status=x").status_code == 400
    assert client.get(f"{BASE}?sort=x").status_code == 400
    assert client.get(f"{BASE}/999").status_code == 404
    assert client.post(f"{BASE}/999/resolve").status_code == 404


def test_club_admin_cannot_see_errors(client, auth_headers):
    assert client.get(BASE, headers=auth_headers).status_code == 403
