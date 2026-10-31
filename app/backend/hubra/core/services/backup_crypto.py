"""How backup files are encrypted and opened.

New backups are encrypted with age to ``BACKUP_PUBLIC_KEY`` (the install's
key) and, for a club backup, also to the club's own key when it has one
(``tenants.backup_public_key``).  The server holds only public keys, so it
can write backups but not read them: verify and restore get the private key
from the operator for that one call, or from ``BACKUP_PRIVATE_KEY`` when an
install chooses to keep it on the server.

Without ``BACKUP_PUBLIC_KEY``, backups are encrypted with the
``BACKUP_ENCRYPTION_KEY`` passphrase (GPG) as before, and ``.gpg`` backups
always open with it.
"""

from __future__ import annotations

import os
import re
import subprocess

from flask import current_app

AGE_SUFFIX = ".dump.age"
GPG_SUFFIX = ".dump.gpg"
AGE_HEADER = b"age-encryption.org/v1\n"

_RECIPIENT = re.compile(r"^age1[02-9ac-hj-np-z]{58}$")
_IDENTITY = re.compile(r"^AGE-SECRET-KEY-1[02-9AC-HJ-NP-Z]{58}$")


class MissingPrivateKey(RuntimeError):
    """Opening this backup needs the backup private key."""


def _stderr(result) -> str:
    return result.stderr.decode("utf-8", errors="replace").strip()


def split_keys(raw: str | None) -> list[str]:
    return [k for k in re.split(r"[\s,]+", raw or "") if k]


def valid_public_key(key: str) -> bool:
    return bool(_RECIPIENT.match(key))


def valid_private_key(key: str) -> bool:
    return bool(_IDENTITY.match(key))


def private_keys_in(text: str | None) -> list[str]:
    """The age private keys in *text* (a pasted key file: comments are fine)."""
    keys = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.append(line)
    return keys


def install_public_keys() -> list[str]:
    return split_keys(current_app.config.get("BACKUP_PUBLIC_KEY"))


def passphrase() -> str:
    return current_app.config.get("BACKUP_ENCRYPTION_KEY", "") or ""


def server_private_key() -> str:
    return current_app.config.get("BACKUP_PRIVATE_KEY", "") or ""


def mode() -> str | None:
    """'age', 'gpg', or None when new backups cannot be encrypted."""
    if install_public_keys():
        return "age"
    if passphrase():
        return "gpg"
    return None


def needs_private_key(s3_key: str | None) -> bool:
    """True when opening this backup needs a key the server does not hold."""
    return bool(s3_key and s3_key.endswith(AGE_SUFFIX)) and not server_private_key()


def encrypt(src: str, dst_base: str, extra_public_keys: list[str]) -> str:
    """Encrypt *src* to ``dst_base`` + suffix; returns the path written."""
    m = mode()
    if m == "age":
        dst = dst_base + AGE_SUFFIX
        cmd = ["age", "--encrypt", "--output", dst]
        for key in [*install_public_keys(), *extra_public_keys]:
            cmd += ["--recipient", key]
        result = subprocess.run([*cmd, src], capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"age encryption failed: {_stderr(result)}")
        return dst
    if m == "gpg":
        dst = dst_base + GPG_SUFFIX
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--quiet",
                "--pinentry-mode",
                "loopback",
                "--passphrase-fd",
                "0",
                "--symmetric",
                "--cipher-algo",
                "AES256",
                "--output",
                dst,
                src,
            ],
            input=passphrase().encode(),
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG encryption failed: {_stderr(result)}")
        return dst
    raise RuntimeError(
        "No backup encryption key: set BACKUP_PUBLIC_KEY "
        "(or the older BACKUP_ENCRYPTION_KEY)"
    )


def decrypt(src: str, dst: str, private_key: str | None = None) -> None:
    """Decrypt *src* (named like its S3 object) into *dst*.

    *private_key* is the operator's age private key for this one call; it
    is written to a file only readable by us, next to *src*, which the
    caller's temporary directory removes.
    """
    if src.endswith(GPG_SUFFIX):
        if not passphrase():
            raise RuntimeError("BACKUP_ENCRYPTION_KEY is not set")
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--quiet",
                "--pinentry-mode",
                "loopback",
                "--passphrase-fd",
                "0",
                "--decrypt",
                "--output",
                dst,
                src,
            ],
            input=passphrase().encode(),
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG decryption failed: {_stderr(result)}")
        return

    keys = private_keys_in(private_key or server_private_key())
    if not keys:
        raise MissingPrivateKey("This backup needs the backup private key")
    if not all(valid_private_key(k) for k in keys):
        raise ValueError("That is not an age private key (AGE-SECRET-KEY-1...)")
    identity = os.path.join(os.path.dirname(dst), "identity.txt")
    fd = os.open(identity, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(keys) + "\n")
        result = subprocess.run(
            ["age", "--decrypt", "--identity", identity, "--output", dst, src],
            capture_output=True,
            timeout=300,
        )
    finally:
        os.remove(identity)
    if result.returncode != 0:
        raise RuntimeError(f"age decryption failed: {_stderr(result)}")


def looks_like_age(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(len(AGE_HEADER)) == AGE_HEADER
