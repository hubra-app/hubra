"""Outgoing webhooks: admins add an address, events arrive signed."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from hubra.core import webhooks
from hubra.core.extensions import db
from hubra.core.models.webhook import Webhook, WebhookDelivery
from tests.authz.conftest import plain_member_token  # noqa: F401
from tests.helpers import add_member

URL = "/api/v1/app/webhooks/"


@pytest.fixture
def public_dns():
    with patch.object(webhooks, "_resolve", return_value=["203.0.113.7"]):
        yield


@pytest.fixture
def sent():
    """Every POST a webhook makes: (url, body, headers); answers 200."""

    class Calls(list):
        status = {"code": 200}

    calls = Calls()
    status = calls.status

    def fake(url, body, headers):
        calls.append((url, body, headers))
        if isinstance(status["code"], Exception):
            raise status["code"]
        return status["code"]

    with patch.object(webhooks, "post", side_effect=fake):
        yield calls


def _create(client, headers, **extra):
    body = {
        "name": "CRM",
        "url": "https://hooks.example.ch/hubra",
        "events": ["member.joined", "member.left", "event.published"],
        **extra,
    }
    return client.post(URL, json=body, headers=headers)


def test_create_shows_the_secret_once(client, auth_headers, public_dns):
    resp = _create(client, auth_headers)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["secret"].startswith("whsec_")
    hook = db.session.get(Webhook, body["id"])
    assert hook.secret != body["secret"]
    assert webhooks.unseal(hook.secret) == body["secret"]
    listed = client.get(URL, headers=auth_headers).get_json()
    assert "secret" not in listed["items"][0]
    assert listed["events"][0] == "member.joined"


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.ch/x",
        "https://user:pw@hooks.example.ch/x",
        "ftp://hooks.example.ch",
        "https://",
    ],
)
def test_only_plain_https(client, auth_headers, public_dns, url):
    resp = _create(client, auth_headers, url=url)
    assert resp.status_code == 400 and resp.get_json()["error"] == "WEBHOOK_URL"


def test_no_private_addresses(client, auth_headers):
    for ip in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1"):
        with patch(
            "socket.getaddrinfo", return_value=[(None, None, None, "", (ip, 443))]
        ):
            resp = _create(client, auth_headers)
        assert resp.status_code == 400, ip
        assert "not a public address" in resp.get_json()["message"]


def test_events_are_checked(client, auth_headers, public_dns):
    assert _create(client, auth_headers, events=[]).status_code == 400
    assert _create(client, auth_headers, events=["member.hacked"]).status_code == 400


def test_admins_only(client, public_dns, plain_member_token):  # noqa: F811
    assert client.get(URL, headers=plain_member_token).status_code == 403
    assert _create(client, plain_member_token).status_code == 403


def test_member_left_arrives_signed(client, auth_headers, public_dns, sent):
    secret = _create(client, auth_headers).get_json()["secret"]
    member_id = add_member(
        client,
        auth_headers,
        email="anna@test.ch",
        first_name="Anna",
        last_name="Muster",
    ).get_json()["id"]
    joined = [c for c in sent if json.loads(c[1])["event"] == "member.joined"]
    assert len(joined) == 1

    resp = client.post(f"/api/v1/members/{member_id}/archive", headers=auth_headers)
    assert resp.status_code == 204
    url, body, headers = sent[-1]
    payload = json.loads(body)
    assert url == "https://hooks.example.ch/hubra"
    assert headers["X-Hubra-Event"] == "member.left" == payload["event"]
    assert payload["object"]["firstName"] == "Anna"
    assert payload["object"]["left"] is not None
    assert payload["data"] == {"member_id": member_id}
    ts, v1 = (p.split("=", 1)[1] for p in headers["X-Hubra-Signature"].split(","))
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    assert v1 == expected.hexdigest()
    assert headers["X-Hubra-Delivery"] == payload["id"]
    delivery = db.session.query(WebhookDelivery).filter_by(uid=payload["id"]).one()
    assert delivery.status == "delivered" and delivery.response_status == 200


def test_only_listed_events_and_active_hooks(client, auth_headers, public_dns, sent):
    hook_id = _create(client, auth_headers, events=["invoice.paid"]).get_json()["id"]
    add_member(
        client, auth_headers, email="ben@test.ch", first_name="Ben", last_name="B"
    )
    assert sent == []
    client.patch(
        f"{URL}{hook_id}",
        json={"events": ["member.joined"], "active": False},
        headers=auth_headers,
    )
    add_member(
        client, auth_headers, email="cleo@test.ch", first_name="Cleo", last_name="C"
    )
    assert sent == []


def test_event_published(client, auth_headers, public_dns, sent):
    _create(client, auth_headers)
    resp = client.post(
        "/api/v1/events/",
        json={"title": "Sommerfest", "date": "2030-06-20", "type": "Social"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    payload = json.loads(sent[-1][1])
    assert payload["event"] == "event.published"
    assert payload["object"]["title"] == "Sommerfest"


def test_failures_retry_then_switch_off(client, auth_headers, public_dns, sent):
    from hubra.core.tasks.webhook_tasks import retry_delivery

    hook_id = _create(client, auth_headers).get_json()["id"]
    sent.status["code"] = 500
    add_member(
        client, auth_headers, email="dana@test.ch", first_name="Dana", last_name="D"
    )
    delivery = db.session.query(WebhookDelivery).one()
    assert delivery.status == "pending" and delivery.error == "HTTP 500"
    for _ in webhooks.RETRY_DELAYS:
        retry_delivery.run(delivery.id)
    db.session.refresh(delivery)
    assert delivery.status == "failed" and delivery.attempts == 4
    assert retry_delivery.run(delivery.id) is False

    hook = db.session.get(Webhook, hook_id)
    hook.failures = webhooks.MAX_FAILURES - 1
    db.session.commit()
    sent.status["code"] = OSError("connection refused")
    resp = client.post(f"{URL}{hook_id}/test", headers=auth_headers)
    assert resp.get_json()["status"] == "failed"
    assert "connection refused" in resp.get_json()["error"]
    db.session.refresh(hook)
    assert hook.active is False and "20 failed" in hook.disabled_reason

    # Switching it back on starts counting again.
    sent.status["code"] = 204
    client.patch(f"{URL}{hook_id}", json={"active": True}, headers=auth_headers)
    db.session.refresh(hook)
    assert hook.active and hook.failures == 0
    resp = client.post(
        f"/api/v1/app/webhooks/deliveries/{delivery.id}/retry", headers=auth_headers
    )
    assert resp.get_json()["status"] == "delivered"


def test_ping_roll_and_delete(client, auth_headers, public_dns, sent):
    created = _create(client, auth_headers).get_json()
    resp = client.post(f"{URL}{created['id']}/test", headers=auth_headers)
    assert resp.get_json()["status"] == "delivered"
    assert sent[-1][2]["X-Hubra-Event"] == "ping"
    rolled = client.post(
        f"{URL}{created['id']}/secret", headers=auth_headers
    ).get_json()
    assert rolled["secret"] != created["secret"]
    rows = client.get(
        f"{URL}{created['id']}/deliveries", headers=auth_headers
    ).get_json()
    assert [r["event"] for r in rows["items"]] == ["ping"]
    assert (
        client.delete(f"{URL}{created['id']}", headers=auth_headers).status_code == 204
    )
    assert db.session.query(WebhookDelivery).count() == 0


def test_a_missing_table_does_not_break_the_caller(client, auth_headers):
    """No webhook, no queued work: emit only looks once and moves on."""
    from hubra.core.modules.events import _webhooks_listening

    assert _webhooks_listening("member.joined", None) is False  # no webhook yet
    assert _webhooks_listening("event.reminder", None) is False  # not offered
