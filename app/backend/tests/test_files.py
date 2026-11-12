"""Hubra's file store (hubra.core.files): club files are encrypted with the
club's key, open only in their club, count towards its storage and go with
the club."""

import os
from unittest.mock import patch

import pytest
from flask import g
from sqlalchemy import select

from hubra.core import files
from hubra.core.models.stored_file import StoredFile
from hubra.core.models.tenant import Tenant
from hubra.core.services import platform_settings


@pytest.fixture
def store(app, tmp_path):
    saved = app.config["FILES_DIR"]
    app.config["FILES_DIR"] = str(tmp_path)
    yield tmp_path
    app.config["FILES_DIR"] = saved


@pytest.fixture
def club(app, db):
    def make(slug: str) -> Tenant:
        tenant = Tenant(name=slug, slug=slug, plan="starter")
        db.session.add(tenant)
        db.session.commit()
        return tenant

    return make


def _in(tenant: Tenant) -> None:
    g._search_path = f"tenant_{tenant.id}, public"


def test_a_file_round_trips_encrypted(app, db, store, club):
    tenant = club("files-a")
    with app.test_request_context():
        _in(tenant)
        stored = files.put("documents", b"Protokoll GV 2026", "text/plain")
        db.session.commit()
        assert stored.key.startswith(f"c{tenant.id}/documents/")
        assert stored.size == len(b"Protokoll GV 2026")
        assert files.read(stored.key) == b"Protokoll GV 2026"

        on_disk = (store / stored.key).read_bytes()
        assert b"Protokoll" not in on_disk
        assert on_disk.startswith(f"hk1.c{tenant.id}.".encode())
        assert files.usage_bytes([tenant.id]) == {tenant.id: stored.size}
        assert files.backend() == "local"


def test_a_file_opens_only_in_its_own_club(app, db, store, club):
    a, b = club("files-b1"), club("files-b2")
    with app.test_request_context():
        _in(a)
        stored = files.put("documents", b"nur fuer A")
        db.session.commit()
        _in(b)
        with pytest.raises(files.FileNotFound):
            files.read(stored.key)
        with pytest.raises(files.FileNotFound):
            files.remove(stored.key)
        # Even with the object copied under B's prefix, A's key can't open it.
        forged = f"c{b.id}/documents/" + stored.key.rsplit("/", 1)[1]
        os.makedirs(store / f"c{b.id}" / "documents", exist_ok=True)
        (store / forged).write_bytes((store / stored.key).read_bytes())
        db.session.add(
            StoredFile(tenant_id=b.id, key=forged, owner="documents", size=1)
        )
        db.session.commit()
        with pytest.raises(files.FileNotFound):
            files.read(forged)


def test_bad_keys_are_not_found(app, db, store, club):
    tenant = club("files-c")
    with app.test_request_context():
        _in(tenant)
        for key in ("", "../etc/passwd", f"c{tenant.id}/documents/../../x", "p/x/y"):
            with pytest.raises(files.FileNotFound):
                files.read(key)


def test_files_above_the_limit_are_refused(app, db, store, club):
    tenant = club("files-d")
    platform_settings.set_many({"files.max_mb": "1"})
    db.session.commit()
    with app.test_request_context():
        _in(tenant)
        with pytest.raises(files.FileTooLarge):
            files.put("documents", b"x" * (1024 * 1024 + 1))
        assert files.put("documents", b"x" * 1024).size == 1024


def test_the_clubs_plan_and_own_limit_decide_the_largest_file(app, db, store, club):
    from hubra.core.services import plans, quotas

    tenant = club("files-d2")
    tenant.plan = "starter"
    platform_settings.set_many({"files.max_mb": "1"})
    plans.update(plans.get("starter"), {"limit_file_mb": 2})
    db.session.commit()
    two_mb = b"x" * (2 * 1024 * 1024)
    with app.test_request_context():
        _in(tenant)
        assert files.max_mb() == 2
        assert files.put("documents", two_mb).size == len(two_mb)
        with pytest.raises(files.FileTooLarge, match="2 MB"):
            files.put("documents", two_mb + b"x")
        quotas.set_overrides(tenant, {"file_mb": 1})
        with pytest.raises(files.FileTooLarge, match="1 MB"):
            files.put("documents", two_mb)


def test_uploads_may_be_larger_than_other_requests(app, client):
    big = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 10)
    resp = client.post(
        "/api/v1/health",
        data=big,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    with app.test_request_context(
        "/x", method="POST", content_type="multipart/form-data; boundary=b", data=b""
    ):
        from flask import request

        from hubra.core.app import _upload_body_limit

        _upload_body_limit()
        assert request.max_content_length == app.config["MAX_UPLOAD_MB"] * 1024 * 1024


def test_remove_deletes_object_and_record(app, db, store, club):
    tenant = club("files-e")
    with app.test_request_context():
        _in(tenant)
        stored = files.put("documents", b"weg damit")
        db.session.commit()
        key = stored.key
        files.remove(key)
        db.session.commit()
        assert not (store / key).exists()
        assert (
            db.session.scalar(select(StoredFile).where(StoredFile.key == key)) is None
        )
        with pytest.raises(files.FileNotFound):
            files.read(key)


def test_deleting_a_club_deletes_its_files(app, db, store, club):
    from hubra.core.tenant.service import TenantService

    gone, kept = club("files-f1"), club("files-f2")
    with app.test_request_context():
        _in(gone)
        a = files.put("documents", b"a").key
        _in(kept)
        b = files.put("documents", b"b").key
        db.session.commit()
        g._search_path = "public"
    assert files.delete_club(gone.id) == 1
    db.session.commit()
    assert not (store / a).exists() and (store / b).exists()
    assert files.usage_bytes([gone.id, kept.id]) == {kept.id: 1}

    # And the permanent club deletion calls it.
    with app.test_request_context():
        _in(kept)
        c = files.put("documents", b"c").key
        db.session.commit()
    with patch("hubra.core.tenant.service.drop_tenant_schema"):
        TenantService.delete_tenant(kept.id, force=True)
    assert not (store / c).exists()


def test_bad_owner_is_refused(app, db, store, club):
    tenant = club("files-g")
    with app.test_request_context():
        _in(tenant)
        with pytest.raises(ValueError):
            files.put("../x", b"x")
