"""Tests for M5 Members module — new fields, search/filter/sort, import, soft delete."""

import io


def _create_member(client, auth_headers, **overrides):
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return client.post("/api/v1/members/", json=payload, headers=auth_headers)


# ── New fields ───────────────────────────────────────────────────────────────


def test_create_member_with_new_fields(client, auth_headers, seeded_db):
    resp = _create_member(
        client,
        auth_headers,
        email="newfields@test.ch",
        phone="+41 79 123 45 67",
        mobile="+41 78 000 00 00",
        birthday="1990-05-15",
        membership_type="regular",
        membership_until="2026-12-31",
        emergency_contact={
            "name": "Jane Doe",
            "phone": "+41 79 999 99 99",
            "relation": "spouse",
        },
        custom_fields={"club_specific": "value"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["phone"] == "+41 79 123 45 67"
    assert body["mobile"] == "+41 78 000 00 00"
    assert body["birthday"] == "1990-05-15"
    assert body["membership_type"] == "regular"
    assert body["membership_until"] == "2026-12-31"
    assert body["emergency_contact"]["name"] == "Jane Doe"
    assert body["custom_fields"]["club_specific"] == "value"


def test_update_member_new_fields(client, auth_headers, seeded_db):
    created = _create_member(client, auth_headers, email="updatefields@test.ch")
    member_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/members/{member_id}",
        json={
            "phone": "+41 79 111 22 33",
            "membership_type": "honorary",
            "birthday": "1985-03-20",
            "custom_fields": {"key1": "val1"},
            "tool_hours": 0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["phone"] == "+41 79 111 22 33"
    assert body["membership_type"] == "honorary"
    assert body["birthday"] == "1985-03-20"
    assert body["custom_fields"]["key1"] == "val1"


def test_create_member_membership_type_validation(client, auth_headers, seeded_db):
    resp = _create_member(
        client,
        auth_headers,
        email="badtype@test.ch",
        membership_type="invalid_type",
    )
    assert resp.status_code == 400


def test_membership_type_defaults_to_regular(client, auth_headers, seeded_db):
    resp = _create_member(client, auth_headers, email="defaults@test.ch")
    assert resp.status_code == 201
    assert resp.get_json()["membership_type"] == "regular"


# ── Search ───────────────────────────────────────────────────────────────────


def test_search_by_phone(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="searchphone@test.ch",
        first_name="Alice",
        last_name="Phone",
        phone="+41 79 555 44 33",
    )
    resp = client.get("/api/v1/members/?search=555+44", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert any(m["email"] == "searchphone@test.ch" for m in body["data"])


def test_search_by_mobile(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="searchmobile@test.ch",
        first_name="Bob",
        last_name="Mobile",
        mobile="+41 78 777 66 55",
    )
    resp = client.get("/api/v1/members/?search=777+66", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert any(m["email"] == "searchmobile@test.ch" for m in body["data"])


# ── Filter ────────────────────────────────────────────────────────────────────


def test_filter_by_membership_type(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="honorary@test.ch",
        first_name="Honorary",
        last_name="Member",
        membership_type="honorary",
    )
    _create_member(
        client,
        auth_headers,
        email="passive@test.ch",
        first_name="Passive",
        last_name="Member",
        membership_type="passive",
    )

    resp = client.get("/api/v1/members/?membership_type=honorary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    for m in body["data"]:
        assert m["membership_type"] == "honorary"
    assert any(m["email"] == "honorary@test.ch" for m in body["data"])


# ── Sort ──────────────────────────────────────────────────────────────────────


def test_sort_by_email_desc(client, auth_headers, seeded_db):
    _create_member(
        client, auth_headers, email="zzz@test.ch", first_name="Zzz", last_name="Test"
    )
    _create_member(
        client, auth_headers, email="aaa@test.ch", first_name="Aaa", last_name="Test"
    )

    resp = client.get("/api/v1/members/?sort=-email&pageSize=100", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    emails = [m["email"] for m in body["data"]]
    assert emails == sorted(emails, reverse=True)


def test_sort_by_first_name(client, auth_headers, seeded_db):
    _create_member(
        client, auth_headers, email="z_first@test.ch", first_name="Zara", last_name="X"
    )
    _create_member(
        client, auth_headers, email="a_first@test.ch", first_name="Anna", last_name="X"
    )

    resp = client.get(
        "/api/v1/members/?sort=first_name&pageSize=100", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    names = [m["first_name"] for m in body["data"]]
    assert names == sorted(names)


def test_invalid_sort_falls_back_to_default(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/members/?sort=invalid_column", headers=auth_headers)
    assert resp.status_code == 200


# ── Export with field selection ───────────────────────────────────────────────


def test_export_with_field_selection(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="export@test.ch",
        phone="+41 79 123 45 67",
    )

    resp = client.get(
        "/api/v1/members/export?fields=first_name,last_name,phone",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    lines = resp.data.decode().strip().split("\n")
    header = lines[0]
    assert "first_name" in header
    assert "last_name" in header
    assert "phone" in header
    assert "email" not in header


def test_export_includes_new_fields(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="export2@test.ch",
        membership_type="honorary",
        phone="+41 79 999 88 77",
    )

    resp = client.get(
        "/api/v1/members/export",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    header = resp.data.decode().split("\n")[0]
    assert "membership_type" in header
    assert "phone" in header
    assert "mobile" in header
    assert "birthday" in header


# ── Soft delete ───────────────────────────────────────────────────────────────


def test_soft_delete_member(client, auth_headers, seeded_db):
    created = _create_member(client, auth_headers, email="softdelete@test.ch")
    member_id = created.get_json()["id"]

    resp = client.delete(f"/api/v1/members/{member_id}/soft", headers=auth_headers)
    assert resp.status_code == 204

    # Should not appear in default list
    resp = client.get("/api/v1/members/", headers=auth_headers)
    body = resp.get_json()
    assert not any(m["id"] == member_id for m in body["data"])

    # Should not be retrievable by default
    resp = client.get(f"/api/v1/members/{member_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_soft_delete_self_prevented(client, auth_headers, seeded_db):
    admin_id = seeded_db["admin"].id
    resp = client.delete(f"/api/v1/members/{admin_id}/soft", headers=auth_headers)
    assert resp.status_code == 403


def test_soft_delete_preserves_data(client, auth_headers, seeded_db, db):
    from vollbuild.core.models.member import Member

    created = _create_member(client, auth_headers, email="preserve@test.ch")
    member_id = created.get_json()["id"]

    client.delete(f"/api/v1/members/{member_id}/soft", headers=auth_headers)

    member = db.session.get(Member, member_id)
    assert member is not None
    assert member.deleted_at is not None
    assert member.email == "preserve@test.ch"


# ── CSV Import ────────────────────────────────────────────────────────────────


def test_import_csv_dry_run(client, auth_headers, seeded_db):
    csv_data = "first_name,last_name,email\nJohn,Doe,john@test.ch\n"
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(csv_data.encode("utf-8")), "test.csv"),
            "dry_run": "true",
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["row_count"] == 1
    assert "first_name" in body["columns"]


def test_import_csv_creates_members(client, auth_headers, seeded_db):
    csv_data = (
        "first_name,last_name,email,phone,membership_type\n"
        "Alice,Smith,alice-import@test.ch,+41 79 111 22 33,regular\n"
        "Bob,Jones,bob-import@test.ch,+41 79 444 55 66,honorary\n"
    )
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(csv_data.encode("utf-8")), "test.csv"),
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert len(body["errors"]) == 0


def test_import_csv_skips_duplicate_emails(client, auth_headers, seeded_db):
    _create_member(
        client,
        auth_headers,
        email="existing@test.ch",
        first_name="Existing",
        last_name="User",
    )

    csv_data = (
        "first_name,last_name,email\n"
        "Alice,Smith,existing@test.ch\n"
        "Bob,Jones,new-import@test.ch\n"
    )
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(csv_data.encode("utf-8")), "test.csv"),
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["created"] == 1
    assert body["skipped"] == 1


def test_import_csv_reports_errors(client, auth_headers, seeded_db):
    csv_data = (
        "first_name,last_name,email\n"
        "Alice,,alice-no-last@test.ch\n"
        ",NoFirst,nofirst@test.ch\n"
        "Bob,Jones,\n"
    )
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(csv_data.encode("utf-8")), "test.csv"),
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["created"] == 0
    assert len(body["errors"]) == 3


def test_import_csv_requires_file(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/members/import",
        data={},
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_import_csv_rejects_non_csv(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/members/import",
        data={
            "file": (io.BytesIO(b"not csv"), "test.txt"),
        },
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    assert resp.status_code == 400
