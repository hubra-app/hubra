"""Details behind the API error-rate alert: error answers per route, exact
status code and ten minutes (perf_monitor.error_details), manage's
/alerts/api-errors, and the alert pointing there."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hubra.core.services import perf_monitor, platform_monitor

BASE = "/api/v1/manager/platform"


@pytest.fixture(autouse=True)
def _fresh():
    from hubra.core.tasks import monitoring

    perf_monitor.reset_local()
    monitoring._alerting_local["on"] = False
    yield
    perf_monitor.reset_local()


def _local():
    return patch("hubra.core.services.perf_monitor._redis", return_value=None)


def test_error_answers_are_kept_per_route_and_exact_code():
    now = datetime(2026, 11, 4, 22, 35, tzinfo=timezone.utc)
    with _local():
        for _ in range(8):
            perf_monitor.record_request("POST /api/v1/a", 500, 5, at=now)
        for _ in range(3):
            perf_monitor.record_request("POST /api/v1/a", 502, 5, at=now)
        perf_monitor.record_request("GET /api/v1/b", 404, 5, at=now)
        perf_monitor.record_request("GET /api/v1/b", 200, 5, at=now)
        # An hour and a half earlier, another route.
        perf_monitor.record_request(
            "GET /api/v1/c", 503, 5, at=now - timedelta(minutes=90)
        )
        out = perf_monitor.error_details(hours=2, now=now)

    assert out["codes"] == {"500": 8, "502": 3, "404": 1, "503": 1}
    routes = {r["label"]: r for r in out["routes"]}
    a = routes["POST /api/v1/a"]
    assert a["serverErrors"] == 11
    assert a["requests"] == 11
    assert a["serverShare"] == 1.0
    assert a["codes"] == {"500": 8, "502": 3}
    assert a["lastAt"] == "2026-11-04T22:30:00+00:00"
    assert routes["GET /api/v1/b"]["clientErrors"] == 1
    assert routes["GET /api/v1/b"]["serverShare"] == 0.0
    # Most server errors first.
    assert out["routes"][0]["label"] == "POST /api/v1/a"
    # Ten-minute timeline from 21:00 to 22:30.
    assert out["timeline"][0]["at"] == "2026-11-04T21:00:00+00:00"
    assert len(out["timeline"]) == 10
    at = {t["at"]: t for t in out["timeline"]}
    assert at["2026-11-04T22:30:00+00:00"]["serverErrors"] == 11
    assert at["2026-11-04T22:30:00+00:00"]["clientErrors"] == 1
    assert at["2026-11-04T21:00:00+00:00"]["serverErrors"] == 1
    # The alert's own window is the last hour only.
    assert out["alert"]["serverErrors"] == 11
    assert [r["route"] for r in out["alert"]["topRoutes"]] == ["/api/v1/a"]


def test_errors_while_starting_are_marked_apart():
    started = perf_monitor._process_started
    perf_monitor._process_started = time.monotonic()
    try:
        with _local():
            perf_monitor.record_request("GET /api/v1/x", 503, 5)
            out = perf_monitor.error_details(hours=1)
    finally:
        perf_monitor._process_started = started
    row = out["routes"][0]
    assert row["codes"] == {"w503": 1}
    assert row["serverErrors"] == 0 and row["warmup"] == 1
    assert out["timeline"][-1]["warmup"] == 1
    assert out["alert"]["topRoutes"] == []


def test_describe_route():
    assert (
        perf_monitor.describe_route(
            {"method": "POST", "route": "/x", "codes": {"500": 12, "502": 3}}
        )
        == "POST /x: 12× 500, 3× 502"
    )


def test_open_problem_links_to_the_details_and_names_the_route(db):
    with _local():
        for i in range(40):
            perf_monitor.record_request("POST /api/v1/a", 500 if i < 10 else 200, 5)
        problem = next(p for p in perf_monitor.problems() if p["id"] == "perf:errors")
    assert problem["link"] == perf_monitor.API_ERRORS_PAGE
    assert "POST /api/v1/a: 10× 500" in problem["detail"]


def test_endpoint_lists_routes_and_their_error_groups(client, staff_headers, db):
    from hubra.core.services import error_tracker

    with _local():
        for _ in range(3):
            perf_monitor.record_request("GET /api/v1/boom", 500, 5)
        try:
            raise ValueError("kaputt")
        except ValueError as exc:
            error_tracker.capture(exc, route="GET /api/v1/boom")
        data = client.get(f"{BASE}/alerts/api-errors?hours=1").get_json()
    row = next(r for r in data["routes"] if r["route"] == "/api/v1/boom")
    assert row["codes"] == {"500": 3}
    assert len(row["errorGroups"]) == 1
    group = data["errorGroups"][0]
    assert group["id"] == row["errorGroups"][0]
    assert group["exc_type"] == "ValueError"


def test_endpoint_is_staff_only(client, auth_headers):
    assert client.get(f"{BASE}/alerts/api-errors").status_code == 403


def test_endpoint_rejects_bad_hours(client, staff_headers):
    assert client.get(f"{BASE}/alerts/api-errors?hours=x").status_code == 400
    assert client.get(f"{BASE}/alerts/api-errors?hours=99").get_json()["hours"] == 24


def test_the_alert_names_the_routes_and_links_the_details(app):
    from hubra.core.tasks.monitoring import check_api_error_rate

    with _local():
        for i in range(60):
            perf_monitor.record_request("POST /api/v1/a", 500 if i < 20 else 200, 5)
        with (
            app.app_context(),
            patch("hubra.core.tasks.monitoring.alert_error") as alert,
        ):
            assert check_api_error_rate()["status"] == "alert"
    kwargs = alert.call_args.kwargs
    assert kwargs["link"] == perf_monitor.API_ERRORS_PAGE
    most = next(f for f in kwargs["fields"] if f["name"] == "Most errors")
    assert most["value"] == "POST /api/v1/a: 20× 500"


def test_link_reaches_the_event_log_and_discord_button(app, db):
    from hubra.core.models.platform_event import PlatformEvent
    from hubra.core.services import platform_bot
    from hubra.core.services.alerts import alert_error

    with patch("hubra.core.services.platform_discord.post_alert") as post:
        alert_error(
            "High API Error Rate", "x", link="/app/platform/diagnostics/api-errors"
        )
    assert post.call_args.kwargs["link"] == "/app/platform/diagnostics/api-errors"
    event = (
        db.session.query(PlatformEvent)
        .filter_by(kind="system.alert")
        .order_by(PlatformEvent.id.desc())
        .first()
    )
    assert event.details["link"] == "/app/platform/diagnostics/api-errors"

    with patch.object(
        platform_bot, "_manage_url", side_effect=lambda p: f"https://manage.example{p}"
    ):
        buttons = platform_bot.alert_buttons(
            "system", link="/app/platform/diagnostics/api-errors"
        )
    link = buttons[0]["components"][-1]
    assert link["url"] == "https://manage.example/app/platform/diagnostics/api-errors"
    assert link["label"] == "Details ansehen"


def test_alert_mail_button_goes_to_the_details(app, db):
    sent = {}

    def body(user, alert_type, subject, lines, level, **kw):
        sent.update(kw)
        return "<p>x</p>", "x", subject

    with (
        patch.object(platform_monitor, "_manage_url", return_value="https://m.example"),
        patch.object(platform_monitor, "_alert_body", side_effect=body),
        patch.object(
            platform_monitor,
            "recipients",
            return_value=[type("U", (), {"email": "s@b.c", "name": "S"})()],
        ),
        patch("hubra.core.services.email._send_via_smtp"),
        patch(
            "hubra.core.services.platform_settings.relay",
            return_value=type("R", (), {"sender_email": "a@b.c", "sender_name": "H"})(),
        ),
    ):
        platform_monitor.deliver_alert(
            "system", "High API Error Rate", ["x"], "error", link="/app/x"
        )
    assert sent["button_url"] == "https://m.example/app/x"
    assert sent["button_key"] == "mail.email.platform_alert.button_details"


def test_one_ten_minute_slot(client, staff_headers, db):
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(minutes=20)
    with _local():
        perf_monitor.record_request("GET /api/v1/old", 500, 5, at=earlier)
        perf_monitor.record_request("GET /api/v1/new", 502, 5, at=now)
        slot = earlier.replace(
            minute=earlier.minute - earlier.minute % 10, second=0, microsecond=0
        )
        data = client.get(
            f"{BASE}/alerts/api-errors?hours=2&at={slot.isoformat().replace('+00:00', 'Z')}"
        ).get_json()
    assert data["at"] == slot.isoformat()
    assert [r["route"] for r in data["routes"]] == ["/api/v1/old"]
    assert data["routes"][0]["requests"] is None
    assert data["codes"] == {"500": 1}
    assert client.get(f"{BASE}/alerts/api-errors?at=nope").status_code == 400
