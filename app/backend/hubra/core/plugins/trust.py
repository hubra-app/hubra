"""Plugin signatures (ported from labdex, same format).

A signed plugin carries SIGNATURE.json next to plugin.yaml:

    {"id": "...", "version": "...", "signer": "Hubra project",
     "key_id": "3f9a…", "files": {"plugin.yaml": "<sha256>", "plugin.py": "<sha256>", …},
     "signature": "<base64 ed25519 signature over the canonical JSON of id, version, files>"}

Trust levels:
    bundled    shipped in the image (plugins/ in the repository)
    official   signed with a key in hubra/core/plugins/keys/official/ (the project's key)
    community  signed with a key an administrator added under Marketplace › Signing keys
    unsigned   no SIGNATURE.json: installs only after an administrator confirms
    invalid    signature doesn't verify, unknown key, or files were changed: never loaded
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SIGFILE = "SIGNATURE.json"
OFFICIAL_DIR = Path(__file__).parent / "keys" / "official"
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def key_id(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def load_public(text: str) -> Ed25519PublicKey:
    text = text.strip()
    if text.startswith("-----BEGIN"):
        key = serialization.load_pem_public_key(text.encode())
    else:  # bare base64 of the 32 raw bytes
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(text))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("not an Ed25519 public key")
    return key


def public_b64(pub: Ed25519PublicKey) -> str:
    return base64.b64encode(
        pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode()


def official_index_url() -> str:
    """Where the official repository lives: HUBRA_OFFICIAL_INDEX, else keys/official/index.url.
    '' = none."""
    import os

    url = os.environ.get("HUBRA_OFFICIAL_INDEX")
    if url is None:
        f = OFFICIAL_DIR / "index.url"
        url = f.read_text().strip() if f.is_file() else ""
    return "" if "OWNER" in url else url.strip()


def official_keys() -> dict[str, tuple[str, Ed25519PublicKey]]:
    out = {}
    if OFFICIAL_DIR.is_dir():
        for f in sorted(OFFICIAL_DIR.glob("*.pub")):
            try:
                k = load_public(f.read_text())
                out[key_id(k)] = (f.stem, k)
            except (ValueError, TypeError):
                continue
    return out


def file_hashes(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if (
            any(part in SKIP_DIRS or part.endswith(".pyc") for part in rel.parts)
            or rel.name == SIGFILE
        ):
            continue
        if p.is_symlink():
            raise ValueError(f"symlinks aren't allowed in plugins ({rel})")
        if p.is_file():
            out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _payload(pid: str, version: str, files: dict) -> bytes:
    return json.dumps(
        {"id": pid, "version": version, "files": files},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def sign(root: Path, private_pem: bytes, signer: str) -> dict:
    import yaml

    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    m = yaml.safe_load((root / "plugin.yaml").read_text()) or {}
    files = file_hashes(root)
    sig = key.sign(_payload(str(m.get("id")), str(m.get("version", "")), files))
    doc = {
        "id": m.get("id"),
        "version": str(m.get("version", "")),
        "signer": signer,
        "key_id": key_id(key.public_key()),
        "files": files,
        "signature": base64.b64encode(sig).decode(),
    }
    (root / SIGFILE).write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def keygen() -> tuple[bytes, str]:
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    return pem, pub


def verify(
    root: Path,
    manifest: dict,
    community: dict[str, tuple[str, Ed25519PublicKey]] | None = None,
) -> dict:
    """{"status", "signer", "key_id", "detail"}"""
    sigfile = root / SIGFILE
    if not sigfile.is_file():
        return {
            "status": "unsigned",
            "signer": "",
            "key_id": "",
            "detail": "no signature",
        }
    try:
        doc = json.loads(sigfile.read_text())
        kid = str(doc["key_id"])
        files = file_hashes(root)
    except (ValueError, KeyError, TypeError) as exc:
        return {
            "status": "invalid",
            "signer": "",
            "key_id": "",
            "detail": f"unreadable signature: {exc}",
        }
    keys = {k: ("official", n, pub) for k, (n, pub) in official_keys().items()}
    keys.update(
        {
            k: ("community", n, pub)
            for k, (n, pub) in (community or {}).items()
            if k not in keys
        }
    )
    if kid not in keys:
        return {
            "status": "invalid",
            "signer": doc.get("signer", ""),
            "key_id": kid,
            "detail": "signed with a key you don't trust",
        }
    level, name, pub = keys[kid]
    if files != doc.get("files"):
        changed = sorted(
            set(files) ^ set(doc.get("files") or {})
            | {
                f
                for f in files
                if (doc.get("files") or {}).get(f) not in (None, files[f])
            }
        )
        return {
            "status": "invalid",
            "signer": doc.get("signer", ""),
            "key_id": kid,
            "detail": f"files differ from what was signed: {', '.join(changed[:6])}",
        }
    if str(doc.get("id")) != str(manifest.get("id")) or str(
        doc.get("version", "")
    ) != str(manifest.get("version", "")):
        return {
            "status": "invalid",
            "signer": doc.get("signer", ""),
            "key_id": kid,
            "detail": "id/version don't match plugin.yaml",
        }
    try:
        pub.verify(
            base64.b64decode(doc["signature"]),
            _payload(doc["id"], doc["version"], files),
        )
    except (InvalidSignature, ValueError):
        return {
            "status": "invalid",
            "signer": doc.get("signer", ""),
            "key_id": kid,
            "detail": "bad signature",
        }
    return {
        "status": level,
        "signer": f"{doc.get('signer') or name}",
        "key_id": kid,
        "detail": f"signed by {name}",
    }


# --------------------------------------------------------------- repositories
INDEX_FIELDS = ("name", "description", "key_id", "public_key", "generated", "plugins")


def _index_payload(doc: dict) -> bytes:
    return json.dumps(
        {k: doc.get(k) for k in INDEX_FIELDS}, sort_keys=True, separators=(",", ":")
    ).encode()


def sign_index(doc: dict, private_pem: bytes) -> dict:
    """Add key_id, public_key and the signature to a repository index."""
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    pub = key.public_key()
    doc = {**doc, "key_id": key_id(pub), "public_key": public_b64(pub)}
    doc["signature"] = base64.b64encode(key.sign(_index_payload(doc))).decode()
    return doc


def verify_index(doc: dict, pub: Ed25519PublicKey) -> None:
    """Raises ValueError unless the index is signed by this key."""
    if not isinstance(doc, dict) or not doc.get("signature"):
        raise ValueError("the index isn't signed")
    if str(doc.get("key_id")) != key_id(pub):
        raise ValueError(
            f"the index is signed with key {doc.get('key_id')}, not the repository's {key_id(pub)}"
        )
    try:
        pub.verify(base64.b64decode(doc["signature"]), _index_payload(doc))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise ValueError("bad index signature") from exc
