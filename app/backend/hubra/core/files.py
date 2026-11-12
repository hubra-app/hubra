"""Hubra's file store: files a club keeps (documents, attachments of plugins).

    from hubra.core import files

    stored = files.put("documents", data, "application/pdf")   # in a club context
    data = files.read(stored.key)
    files.remove(stored.key)

Every file is encrypted with its club's data key (AES-256-GCM, see
``hubra.core.crypto.encrypt_bytes``) before it leaves the process, so the
store only ever holds ciphertext, and a file opens only in its own club:
reading another club's key fails like a missing file.

Where files go is the platform's choice (manage › Backups › Storage, the
``files.*`` platform settings): an S3 bucket when ``files.s3.bucket`` is set,
otherwise the folder ``FILES_DIR`` on the server, which only suits a single
server (several replicas need S3).

Each file has a record in ``stored_files`` (public schema): it counts towards
the club's storage and lets ``delete_club`` remove a deleted club's files.
``put`` adds the record to the session, so it is saved with the caller's
commit; a rollback leaves the object behind without a record (it is
encrypted and counts nowhere).
"""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass

from flask import current_app
from sqlalchemy import delete, func, select

from hubra.core import crypto
from hubra.core.extensions import db
from hubra.core.models.stored_file import StoredFile

_OWNER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_KEY = re.compile(r"^(c\d+|p)/[a-z][a-z0-9_-]{0,63}/[0-9a-f]{32}$")


class FileStoreError(Exception):
    """The store is unreachable or refused the file."""


class FileTooLarge(FileStoreError):
    """The file is larger than the club may upload (``max_mb``: its own
    limit, its plan's, or ``files.max_mb``)."""


class FileNotFound(FileStoreError):
    """No such file in this club."""


# ── Settings ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _S3:
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str


def _s3_config() -> _S3 | None:
    from hubra.core.services import platform_settings as ps

    bucket = ps.get("files.s3.bucket")
    if not bucket:
        return None
    return _S3(
        endpoint=ps.get("files.s3.endpoint"),
        bucket=bucket,
        region=ps.get("files.s3.region") or "default",
        access_key=ps.get("files.s3.access_key"),
        secret_key=ps.get("files.s3.secret_key"),
    )


def max_mb(tenant_id: int | None = None) -> int:
    """The largest file, in MB, the club (default: the one this context
    works in) can store: its own limit, its plan's, else ``files.max_mb``;
    never more than the server's upload ceiling (``services.quotas``)."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import quotas

    if tenant_id is None:
        tenant_id = _tenant_of(crypto.context_scope())
    tenant = db.session.get(Tenant, tenant_id) if tenant_id is not None else None
    return quotas.max_file_mb(tenant)


def max_bytes(tenant_id: int | None = None) -> int:
    return max_mb(tenant_id) * 1024 * 1024


def backend() -> str:
    """``s3`` or ``local``."""
    return "s3" if _s3_config() else "local"


# ── Backends ─────────────────────────────────────────────────────────────────


def _client(cfg: _S3):
    import boto3  # noqa: PLC0415

    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint or None,
        region_name=cfg.region,
        aws_access_key_id=cfg.access_key or None,
        aws_secret_access_key=cfg.secret_key or None,
    )


def _local_path(key: str) -> str:
    # _KEY allows no dots or slashes beyond the two separators, so the path
    # stays inside FILES_DIR.
    return os.path.join(current_app.config["FILES_DIR"], *key.split("/"))


def _write(key: str, blob: bytes) -> None:
    cfg = _s3_config()
    try:
        if cfg:
            _client(cfg).put_object(Bucket=cfg.bucket, Key=key, Body=blob)
            return
        path = _local_path(key)
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "wb") as f:
            f.write(blob)
    except Exception as err:  # boto3/OS errors of every kind
        raise FileStoreError(f"could not store the file: {type(err).__name__}") from err


def _read(key: str) -> bytes:
    cfg = _s3_config()
    try:
        if cfg:
            return _client(cfg).get_object(Bucket=cfg.bucket, Key=key)["Body"].read()
        with open(_local_path(key), "rb") as f:
            return f.read()
    except FileNotFoundError as err:
        raise FileNotFound(key) from err
    except Exception as err:
        if type(err).__name__ == "NoSuchKey":
            raise FileNotFound(key) from err
        raise FileStoreError(f"could not read the file: {type(err).__name__}") from err


def _unlink(keys: list[str]) -> None:
    if not keys:
        return
    cfg = _s3_config()
    try:
        if cfg:
            client = _client(cfg)
            for i in range(0, len(keys), 1000):
                client.delete_objects(
                    Bucket=cfg.bucket,
                    Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]]},
                )
            return
        for key in keys:
            try:
                os.remove(_local_path(key))
            except FileNotFoundError:
                pass
    except Exception as err:
        raise FileStoreError(f"could not delete files: {type(err).__name__}") from err


# ── API ──────────────────────────────────────────────────────────────────────


def _tenant_of(scope: str) -> int | None:
    return int(scope[1:]) if scope.startswith("c") else None


def _purpose(owner: str) -> str:
    return f"files.{owner}"


def put(
    owner: str, data: bytes, content_type: str = "application/octet-stream"
) -> StoredFile:
    """Store *data* for the club this context works in; returns its record
    (added to the session, saved with the caller's commit)."""
    if not _OWNER.match(owner):
        raise ValueError(f"bad owner {owner!r}")
    scope = crypto.context_scope()
    limit = max_mb(_tenant_of(scope))
    if len(data) > limit * 1024 * 1024:
        raise FileTooLarge(f"larger than {limit} MB")
    key = f"{scope}/{owner}/{secrets.token_hex(16)}"
    _write(key, crypto.encrypt_bytes(data, _purpose(owner), scope))
    record = StoredFile(
        tenant_id=_tenant_of(scope),
        key=key,
        owner=owner,
        size=len(data),
        content_type=(content_type or "application/octet-stream")[:255],
    )
    db.session.add(record)
    db.session.flush()
    return record


def _own_record(key: str) -> StoredFile:
    scope = crypto.context_scope()
    if not _KEY.match(key or "") or not key.startswith(f"{scope}/"):
        raise FileNotFound(key)
    record = db.session.scalar(select(StoredFile).where(StoredFile.key == key))
    if record is None:
        raise FileNotFound(key)
    return record


def read(key: str) -> bytes:
    """The bytes of a file of this club; ``FileNotFound`` for anything else."""
    record = _own_record(key)
    try:
        return crypto.decrypt_bytes(_read(key), _purpose(record.owner))
    except crypto.InvalidToken as err:
        raise FileNotFound(key) from err


def info(key: str) -> StoredFile:
    return _own_record(key)


def remove(key: str) -> None:
    """Delete a file of this club (object now, record with the commit)."""
    record = _own_record(key)
    _unlink([key])
    db.session.delete(record)


def delete_club(tenant_id: int) -> int:
    """Delete every file of a club (when the club is deleted for good)."""
    keys = list(
        db.session.scalars(
            select(StoredFile.key).where(StoredFile.tenant_id == tenant_id)
        )
    )
    _unlink(keys)
    db.session.execute(delete(StoredFile).where(StoredFile.tenant_id == tenant_id))
    return len(keys)


def usage_bytes(tenant_ids: list[int]) -> dict[int, int]:
    """Bytes stored per club (plaintext size)."""
    if not tenant_ids:
        return {}
    rows = db.session.execute(
        select(StoredFile.tenant_id, func.coalesce(func.sum(StoredFile.size), 0))
        .where(StoredFile.tenant_id.in_(tenant_ids))
        .group_by(StoredFile.tenant_id)
    )
    return {tid: int(total) for tid, total in rows}


def status() -> dict:
    """Where files go and whether that works (for manage's diagnostics)."""
    cfg = _s3_config()
    out = {"backend": "s3" if cfg else "local", "reachable": False, "error": None}
    try:
        if cfg:
            _client(cfg).head_bucket(Bucket=cfg.bucket)
        else:
            os.makedirs(current_app.config["FILES_DIR"], mode=0o700, exist_ok=True)
            if not os.access(current_app.config["FILES_DIR"], os.W_OK):
                raise PermissionError("FILES_DIR is not writable")
        out["reachable"] = True
    except Exception as err:
        out["error"] = type(err).__name__
    return out
