"""A tiny Kubernetes API client for the objects Hubra manages itself.

Only used for custom domains (``hubra.core.services.domain_serving``): one
Ingress and one cert-manager Certificate per verified club domain. It talks
to the API with the pod's service account (mounted token, CA and namespace),
so it works only inside the cluster and only as far as that account's Role
allows (deploy/app/domains-rbac.yaml: ingresses and certificates in Hubra's
namespace). Outside a cluster :func:`available` is False and nothing runs.

Objects are written with server-side apply (field manager ``hubra``), so a
run that changes nothing changes nothing.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
FIELD_MANAGER = "hubra"
TIMEOUT = 15

# kind -> (API group path, plural)
KINDS = {
    "Ingress": ("/apis/networking.k8s.io/v1", "ingresses"),
    "Certificate": ("/apis/cert-manager.io/v1", "certificates"),
}


class KubeError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _read(name: str) -> str:
    with open(os.path.join(SA_DIR, name), encoding="utf-8") as fh:
        return fh.read().strip()


def available() -> bool:
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST")) and os.path.isfile(
        os.path.join(SA_DIR, "token")
    )


def namespace() -> str:
    return os.environ.get("HUBRA_NAMESPACE") or _read("namespace")


def _send(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    """One HTTP request to the API server; tests replace this."""
    ctx = ssl.create_default_context(cafile=os.path.join(SA_DIR, "ca.crt"))
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _call(
    method: str,
    path: str,
    body: dict | None = None,
    content_type: str = "application/json",
    query: dict | None = None,
) -> dict[str, Any]:
    host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    if ":" in host:  # IPv6
        host = f"[{host}]"
    url = f"https://{host}:{port}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Authorization": f"Bearer {_read('token')}",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = content_type
    try:
        status, raw = _send(method, url, headers, data)
    except OSError as exc:
        raise KubeError(f"Kubernetes API not reachable: {exc}") from exc
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    if status >= 400:
        raise KubeError(
            payload.get("message") or f"Kubernetes answered {status}", status
        )
    return payload


def _base(kind: str) -> str:
    group, plural = KINDS[kind]
    return f"{group}/namespaces/{urllib.parse.quote(namespace())}/{plural}"


def list_objects(kind: str, selector: str) -> list[dict]:
    return _call("GET", _base(kind), query={"labelSelector": selector}).get("items", [])


def apply(obj: dict) -> dict:
    name = obj["metadata"]["name"]
    return _call(
        "PATCH",
        f"{_base(obj['kind'])}/{urllib.parse.quote(name)}",
        obj,
        content_type="application/apply-patch+yaml",
        query={"fieldManager": FIELD_MANAGER, "force": "true"},
    )


def delete(kind: str, name: str) -> None:
    try:
        _call("DELETE", f"{_base(kind)}/{urllib.parse.quote(name)}")
    except KubeError as exc:
        if exc.status != 404:
            raise
