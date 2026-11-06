"""Posts in several languages: the post's language, its translations and
machine translation through DeepL (services.content_languages,
services.machine_translation)."""

from __future__ import annotations

import io
import json
from unittest.mock import patch


def _create(client, headers, **extra):
    body = {"title": "Saisonstart", "body": "Am Samstag geht es los.", **extra}
    return client.post("/api/v1/posts/", json=body, headers=headers)


def test_post_keeps_its_language_and_translations(client, auth_headers, seeded_db):
    resp = _create(
        client,
        auth_headers,
        language="de",
        translations={
            "fr": {"title": "Début de saison", "body": "Ça commence samedi."},
            "it": {"title": "", "body": ""},
        },
    )
    assert resp.status_code == 201, resp.get_json()
    post = resp.get_json()
    assert post["language"] == "de"
    # An empty language is no translation.
    assert set(post["translations"]) == {"fr"}
    assert post["translations"]["fr"]["summary"] is None

    patched = client.patch(
        f"/api/v1/posts/{post['id']}",
        json={"translations": {"en": {"title": "Season start", "body": "Saturday."}}},
        headers=auth_headers,
    ).get_json()
    assert set(patched["translations"]) == {"en"}


def test_translations_are_checked(client, auth_headers, seeded_db):
    bad = [
        {"xx": {"title": "a", "body": "b"}},
        {"de": {"title": "a", "body": "b"}},  # the post's own language
        {"fr": {"title": "Nur Titel", "body": ""}},
        {"fr": {"title": "a", "body": "b", "author": "x"}},
        {"fr": {"title": "a" * 256, "body": "b"}},
    ]
    for translations in bad:
        resp = _create(client, auth_headers, language="de", translations=translations)
        assert resp.status_code == 400, translations
    assert _create(client, auth_headers, language="xx").status_code == 400

    post_id = _create(client, auth_headers, language="de").get_json()["id"]
    resp = client.patch(
        f"/api/v1/posts/{post_id}",
        json={"translations": {"de": {"title": "a", "body": "b"}}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_machine_translation_is_off_without_a_key(client, auth_headers, seeded_db):
    assert client.get("/api/v1/posts/translate", headers=auth_headers).get_json()[
        "available"
    ] is False
    resp = client.post(
        "/api/v1/posts/translate",
        json={"target": "fr", "title": "Hallo", "body": "Welt"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_machine_translation_through_deepl(client, auth_headers, seeded_db, app):
    from hubra.core.services import platform_settings

    platform_settings.set_many({"translate.deepl_key": "test-key:fx"})
    from hubra.core.extensions import db

    db.session.commit()
    sent = {}

    def fake_urlopen(req, timeout):
        sent["url"] = req.full_url
        sent["auth"] = req.headers["Authorization"]
        sent["body"] = json.loads(req.data)
        texts = sent["body"]["text"]
        return _Resp(json.dumps({"translations": [{"text": f"FR:{t}"} for t in texts]}).encode())

    with patch("urllib.request.urlopen", fake_urlopen):
        resp = client.post(
            "/api/v1/posts/translate",
            json={"target": "fr", "source": "de", "title": "Hallo", "summary": "", "body": "**Welt**"},
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json() == {"title": "FR:Hallo", "summary": None, "body": "FR:**Welt**"}
    assert sent["url"] == "https://api-free.deepl.com/v2/translate"
    assert sent["auth"] == "DeepL-Auth-Key test-key:fx"
    # Empty fields are not sent.
    assert sent["body"] == {"text": ["Hallo", "**Welt**"], "target_lang": "FR", "source_lang": "DE"}
    assert client.get("/api/v1/posts/translate", headers=auth_headers).get_json()["available"]
