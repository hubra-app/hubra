"""A translations CSV from the export can be imported again as it is."""

import io

from hubra.api.i18n.services import get_translations


def test_export_then_import_adds_no_header_row(client, auth_headers, seeded_db):
    client.patch(
        "/api/v1/i18n/de-CH",
        json=[{"key": "nav.home", "value": "Startseite"}],
        headers=auth_headers,
    )
    exported = client.get(
        "/api/v1/i18n/de-CH/export?format=csv", headers=auth_headers
    ).get_data()

    # As Excel saves it: with a byte order mark.
    resp = client.post(
        "/api/v1/i18n/de-CH/import?format=csv",
        data={"file": (io.BytesIO("﻿".encode() + exported), "de.csv")},
        headers=auth_headers,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.get_json()
    keys = {t.key for t in get_translations("de-CH")}
    assert "key" not in keys
    assert "﻿key" not in keys
    assert "nav.home" in keys
