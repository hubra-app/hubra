"""The member export is separated with ';' (as German and Swiss Excel open
CSV), and the import reads it back."""

import io


def test_export_uses_semicolons_and_imports_back(client, auth_headers, seeded_db):
    resp = client.get(
        "/api/v1/members/export?fields=first_name,last_name,email",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    header = text.splitlines()[0]
    assert header == "first_name;last_name;email"

    back = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(resp.data), "export.csv"),
            "dry_run": "true",
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert back.status_code == 200
    first = back.get_json()["preview"][0]
    assert "@" in first["email"]
