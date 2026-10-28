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
