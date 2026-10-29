"""The translation editor's write routes: duplicate, copy defaults, delete,
missing-key reports and the flagged list."""

from hubra.api.i18n.services import get_translations

URL = "/api/v1/i18n"


def _values(locale):
    return {t.key: t.value for t in get_translations(locale)}


def _seed(client, auth_headers):
    client.patch(
        f"{URL}/de",
        json=[
            {"key": "nav.home", "value": "Startseite"},
            {"key": "nav.events", "value": "Anlässe"},
        ],
        headers=auth_headers,
    )


def test_duplicate_a_language(client, auth_headers, seeded_db):
    _seed(client, auth_headers)
    client.patch(
        f"{URL}/fr",
        json=[{"key": "nav.home", "value": "Accueil"}],
        headers=auth_headers,
    )

    resp = client.post(
        f"{URL}/fr/duplicate", json={"source": "de"}, headers=auth_headers
    )
    assert resp.status_code == 201 and resp.get_json()["inserted"] == 1
    # Keys it already had stay; the others come in empty, to be translated.
    assert _values("fr") == {"nav.home": "Accueil", "nav.events": ""}

    resp = client.post(
        f"{URL}/it/duplicate",
        json={"source": "de", "copy_values": True},
        headers=auth_headers,
    )
    assert _values("it") == _values("de")


def test_duplicate_needs_a_different_existing_source(client, auth_headers, seeded_db):
    _seed(client, auth_headers)
    assert (
        client.post(
            f"{URL}/de/duplicate", json={"source": "de"}, headers=auth_headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{URL}/fr/duplicate", json={"source": "xx"}, headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.post(f"{URL}/fr/duplicate", json={}, headers=auth_headers).status_code
        == 400
    )


def test_reported_keys_are_flagged_and_defaults_fill_them(
    client, auth_headers, seeded_db
):
    _seed(client, auth_headers)
    resp = client.post(
        f"{URL}/de/report",
        json={
            "keys": [
                {"key": "nav.polls", "default_value": "Umfragen"},
                {"key": "nav.home", "default_value": "Start"},
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    flagged = client.get(f"{URL}/de/flagged", headers=auth_headers).get_json()
    assert [f["key"] for f in flagged] == ["nav.polls"]
    assert flagged[0]["is_missing"] is True

    resp = client.post(f"{URL}/de/copy-defaults", headers=auth_headers)
    assert resp.get_json()["filled"] == 1
    values = _values("de")
    # The missing key gets its default; a translated one keeps its text.
    assert values["nav.polls"] == "Umfragen" and values["nav.home"] == "Startseite"
    assert client.get(f"{URL}/de/flagged", headers=auth_headers).get_json() == []


def test_deleting_a_key_takes_its_aliases(client, auth_headers, seeded_db):
    _seed(client, auth_headers)
    client.post(
        f"{URL}/de",
        json={"key": "menu.home", "value": "", "alias_for": "nav.home"},
        headers=auth_headers,
    )
    resp = client.delete(f"{URL}/de/nav.home", headers=auth_headers)
    assert resp.status_code == 200 and resp.get_json()["count"] == 2
    assert set(_values("de")) == {"nav.events"}
    assert client.delete(f"{URL}/de/nav.home", headers=auth_headers).status_code == 404
