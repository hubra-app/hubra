"""Member CSV import reads the files spreadsheets actually save."""

import io


def test_import_reads_a_windows_1252_csv(client, auth_headers, seeded_db):
    """Excel on Windows saves CSV as Windows-1252; that used to be a 500."""
    csv_data = "first_name,last_name,email\nZoë,Müller,zoe@test.ch\n"
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(csv_data.encode("cp1252")), "export.csv"),
            "dry_run": "true",
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["preview"][0]["last_name"] == "Müller"


def _post(client, auth_headers, csv_data, **form):
    return client.post(
        "/api/v1/members/import",
        data={"file": (io.BytesIO(csv_data.encode()), "export.csv"), **form},
        content_type="multipart/form-data",
        headers=auth_headers,
    )


def test_a_list_too_long_for_one_request_is_refused(client, auth_headers, seeded_db):
    from hubra.api.members.routes import MAX_IMPORT_ROWS

    rows = "".join(f"x{i}@test.ch\n" for i in range(MAX_IMPORT_ROWS + 1))
    resp = _post(client, auth_headers, "email\n" + rows)
    assert resp.status_code == 400
    assert str(MAX_IMPORT_ROWS) in resp.get_json()["message"]


def test_a_mapping_that_is_not_an_object_is_a_400(client, auth_headers, seeded_db):
    for mapping in ("[1]", '{"Mail": 1}', '"email"'):
        resp = _post(client, auth_headers, "Mail\nx@test.ch\n", mapping=mapping)
        assert resp.status_code == 400, mapping


def test_semicolon_csv_from_a_swiss_excel(client, auth_headers, seeded_db):
    """Excel with a German or Swiss locale separates fields with ';'."""
    resp = _post(
        client,
        auth_headers,
        "first_name;last_name;email\nAnna;Muster;anna@test.ch\n",
        dry_run="true",
    )
    assert resp.status_code == 200
    row = resp.get_json()["preview"][0]
    assert row["email"] == "anna@test.ch" and row["last_name"] == "Muster"
