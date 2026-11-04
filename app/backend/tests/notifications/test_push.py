"""Browser push: subscriptions, encryption and signing, and every bell
notification going out as a push."""

import base64
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from hubra.core.models.push_subscription import PushSubscription
from hubra.core.services import notification_text, web_push

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@pytest.fixture
def browser():
    """A browser's subscription keys: its P-256 key pair and auth secret."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return key, _b64(public), _b64(b"0123456789abcdef")


# ── The protocol ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,ok",
    [
        (ENDPOINT, True),
        ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
        ("https://web.push.apple.com/QGx", True),
        ("https://wns2-db5p.notify.windows.com/w/?token=x", True),
        ("http://fcm.googleapis.com/fcm/send/x", False),
        ("https://fcm.googleapis.com:8443/x", False),
        ("https://evil.example/fcm.googleapis.com", False),
        ("https://fcm.googleapis.com.evil.example/x", False),
        ("https://169.254.169.254/latest", False),
        ("", False),
        (None, False),
    ],
)
def test_only_browser_push_services_are_called(url, ok):
    assert web_push.is_push_endpoint(url) is ok


def test_a_push_only_the_browser_can_read(browser):
    import http_ece

    key, p256dh, auth = browser
    assert web_push.valid_keys(p256dh, auth)
    assert not web_push.valid_keys("bm90IGEga2V5", auth)
    assert not web_push.valid_keys(p256dh, _b64(b"short"))

    sealed = web_push.encrypt(b'{"title": "Hallo"}', p256dh, auth)
    opened = http_ece.decrypt(
        sealed, private_key=key, auth_secret=_unb64(auth), version="aes128gcm"
    )
    assert json.loads(opened) == {"title": "Hallo"}


def test_requests_are_signed_with_the_platform_key():
    public, private = web_push.generate_vapid_keys()
    header = web_push._vapid_header(ENDPOINT, private, "mailto:a@b.ch")
    token, k = re.fullmatch(r"vapid t=(\S+), ?k=(\S+)", header).groups()
    assert k == public
    head, claims, signature = token.split(".")
    payload = json.loads(_unb64(claims))
    assert payload["aud"] == "https://fcm.googleapis.com"
    assert payload["sub"] == "mailto:a@b.ch"
    raw = _unb64(signature)
    der = encode_dss_signature(
        int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    )
    key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _unb64(public))
    key.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


# ── Subscribing ───────────────────────────────────────────────────────────────


def test_subscribe_and_unsubscribe_this_device(client, auth_headers, db, browser):
    _, p256dh, auth = browser
    setup = client.get(f"/api/v1/account/push?endpoint={ENDPOINT}").get_json()
    assert setup["subscribed"] is False
    assert len(_unb64(setup["public_key"])) == 65
    # The key pair is made once.
    assert client.get("/api/v1/account/push").get_json()["public_key"] == setup["public_key"]

    bad = {"endpoint": "https://evil.example/x", "keys": {"p256dh": p256dh, "auth": auth}}
    assert client.post("/api/v1/account/push", json=bad).status_code == 422
    bad = {"endpoint": ENDPOINT, "keys": {"p256dh": "x", "auth": auth}}
    assert client.post("/api/v1/account/push", json=bad).status_code == 422

    body = {"endpoint": ENDPOINT, "keys": {"p256dh": p256dh, "auth": auth}}
    assert client.post("/api/v1/account/push", json=body).status_code == 201
    assert client.post("/api/v1/account/push", json=body).status_code == 201  # same row
    assert db.session.query(PushSubscription).count() == 1
    assert client.get(f"/api/v1/account/push?endpoint={ENDPOINT}").get_json()["subscribed"]

    assert client.delete("/api/v1/account/push", json={"endpoint": ENDPOINT}).status_code == 204
    assert db.session.query(PushSubscription).count() == 0


def test_push_needs_an_account(client):
    assert client.get("/api/v1/account/push").status_code == 401


# ── Every bell notification goes out ──────────────────────────────────────────


@pytest.fixture
def device(db, seeded_db, browser):
    from hubra.core.services import platform_settings

    platform_settings.web_push(create=True)
    _, p256dh, auth = browser
    row = PushSubscription(
        user_id=seeded_db["user"].id, endpoint=ENDPOINT, p256dh=p256dh, auth=auth
    )
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture
def queued():
    """Queued push tasks, run by ``run()`` after the commit as the worker
    would (an eager task inside the commit hook could not use the session)."""
    from hubra.core.notifications.push import deliver

    with patch("hubra.core.tasks.push_tasks.send_push_task.delay") as delay:

        def run():
            for call in delay.call_args_list:
                deliver(**call.kwargs)
            delay.reset_mock()

        run.delay = delay
        yield run


def test_a_notification_is_pushed_in_the_members_language(db, seeded_db, device, queued):
    from hubra.core.notifications.services import notify_member

    with patch.object(
        web_push, "send", return_value=web_push.PushResult(ok=True, status=201)
    ) as send:
        notify_member(
            seeded_db["admin"].id,
            "warning",
            "Reminder: Neues Vereinslokal?",
            "Please cast your vote before the poll closes.",
            link="/app/operations/polls?poll=3",
        )
        db.session.flush()
        assert queued.delay.call_count == 0  # not before the commit
        db.session.commit()
        queued()

    assert send.call_count == 1
    sub, message, _keys = send.call_args.args
    assert sub.endpoint == ENDPOINT
    assert message["title"] == "Erinnerung: Neues Vereinslokal?"
    assert message["body"] == "Bitte stimme ab, bevor die Umfrage schliesst."
    assert message["url"] == "/app/operations/polls?poll=3"
    db.session.refresh(device)
    assert device.last_used_at is not None


def test_english_reader_and_a_foreign_link(db, seeded_db, device, queued):
    from hubra.core.notifications.services import notify_member

    seeded_db["user"].language = "en-GB"
    db.session.commit()
    with patch.object(web_push, "send", return_value=web_push.PushResult(ok=True)) as send:
        notify_member(seeded_db["admin"].id, "info", "Event reminder", "Fest", link="https://evil.example")
        db.session.commit()
        queued()
    message = send.call_args.args[1]
    assert (message["title"], message["body"]) == ("Event reminder", "Fest")
    assert message["url"] == "/app/dashboard"


def test_a_rolled_back_notification_is_not_pushed(db, seeded_db, device, queued):
    from hubra.core.notifications.services import notify_member

    with patch.object(web_push, "send") as send:
        notify_member(seeded_db["admin"].id, "info", "New post", "x")
        db.session.flush()
        db.session.rollback()
        db.session.commit()
        queued()
    send.assert_not_called()
    queued.delay.assert_not_called()


def test_a_device_that_is_gone_is_removed(db, seeded_db, device, queued):
    from hubra.core.notifications.services import notify_member

    with patch.object(web_push, "send", return_value=web_push.PushResult(ok=False, gone=True, status=410)):
        notify_member(seeded_db["admin"].id, "info", "New post", "x")
        db.session.commit()
        queued()
    assert db.session.query(PushSubscription).count() == 0


def test_nobody_with_a_device_means_no_task(db, seeded_db):
    from hubra.core.notifications.services import notify_member

    with patch("hubra.core.tasks.push_tasks.send_push_task.delay") as delay:
        notify_member(seeded_db["admin"].id, "info", "New post", "x")
        db.session.commit()
    delay.assert_not_called()


# ── The text table matches the apps' ──────────────────────────────────────────

_TS = Path(__file__).resolve().parents[4] / "packages/ui/src/notificationText.ts"


@pytest.mark.skipif(not _TS.exists(), reason="packages/ui not in this checkout")
def test_push_texts_match_the_apps_texts():
    source = _TS.read_text()
    titles = dict(re.findall(r"^  '([^']+)': \[\s*'(shell\.notif\.text\.\w+)'", source, re.M))
    assert titles == {k: v[0] for k, v in notification_text.TITLES.items()}
    prefixes = re.findall(r"\['([^']+: )', '(shell\.notif\.text\.\w+)'", source)
    assert prefixes == [(p, k) for p, k, _, _ in notification_text.PREFIXES]
    message_keys = re.findall(r"key: '(shell\.notif\.text\.\w+)'", source)
    assert message_keys == [k for _, k, _, _ in notification_text.MESSAGES]
