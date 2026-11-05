"""Serving visitors on verified club domains (k3s with cert-manager).

A club points its domain (``verein.ch`` or ``mitglieder.fcx.ch``) at the
platform with a CNAME and verifies it with the TXT record
(``domain_tasks``). From then on :func:`reconcile`, which the platform
worker runs every two minutes, keeps one cert-manager Certificate and, once
that certificate is issued, one Ingress per verified domain in Hubra's
namespace. The Ingress routes the domain to ``domains.service`` (the global
backend), where :func:`install` sends every request on to the club in the
club app: ``https://verein.ch/events`` → ``<app>/<club>/events``. Sign-in
stays on the platform's own hosts.

Rules:

- Only objects carrying ``LABEL`` are touched, so hand-made Ingresses and
  Flux's own objects are never changed or removed.
- The Ingress comes only after the certificate is Ready, so a visitor never
  sees the cluster's default certificate.
- A domain whose certificate isn't Ready after a day is ``failed`` and one
  system alert goes out; it keeps being tried.
- ``domains.serving`` off is the kill switch: every managed Ingress is
  removed at the next run (certificates stay, so switching on again doesn't
  hit the issuer's rate limits).
- A domain that is no longer verified (or deleted, or its club gone) loses
  its Ingress and Certificate.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, current_app, redirect, request
from sqlalchemy import select

from hubra.core import kube
from hubra.core.extensions import db
from hubra.core.models.domain import Domain
from hubra.core.models.tenant import Tenant
from hubra.core.services import platform_settings

_log = logging.getLogger(__name__)

LABEL = "hubra.club/club-domain"
ALERT_AFTER = timedelta(hours=24)
# How long a process keeps its list of served domains before asking again.
HOSTS_TTL = 60.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def object_name(domain: str) -> str:
    """A stable Kubernetes name for *domain* (names can't hold every host)."""
    return "club-domain-" + hashlib.sha256(domain.encode()).hexdigest()[:16]


def serving_on() -> bool:
    return platform_settings.get("domains.serving") == "on"


def _settings() -> dict[str, str]:
    return {
        "issuer": platform_settings.get("domains.cluster_issuer") or "letsencrypt",
        "ingress_class": platform_settings.get("domains.ingress_class") or "traefik",
        "service": platform_settings.get("domains.service") or "global-backend",
    }


def _labels(domain: Domain) -> dict[str, str]:
    return {
        LABEL: "true",
        "app.kubernetes.io/managed-by": "hubra",
        "app.kubernetes.io/part-of": "hubra",
        "hubra.club/club": str(domain.tenant_id),
    }


def certificate(domain: Domain, cfg: dict[str, str]) -> dict:
    name = object_name(domain.domain)
    return {
        "apiVersion": "cert-manager.io/v1",
        "kind": "Certificate",
        "metadata": {
            "name": name,
            "labels": _labels(domain),
            "annotations": {"hubra.club/domain": domain.domain},
        },
        "spec": {
            "secretName": f"{name}-tls",
            "dnsNames": [domain.domain],
            "issuerRef": {"name": cfg["issuer"], "kind": "ClusterIssuer"},
        },
    }


def ingress(domain: Domain, cfg: dict[str, str]) -> dict:
    name = object_name(domain.domain)
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": name,
            "labels": _labels(domain),
            "annotations": {
                "hubra.club/domain": domain.domain,
                "traefik.ingress.kubernetes.io/router.entrypoints": "websecure",
                "traefik.ingress.kubernetes.io/router.tls": "true",
            },
        },
        "spec": {
            "ingressClassName": cfg["ingress_class"],
            "tls": [{"secretName": f"{name}-tls", "hosts": [domain.domain]}],
            "rules": [
                {
                    "host": domain.domain,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": cfg["service"],
                                        "port": {"name": "http"},
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
        },
    }


def _ready(cert: dict | None) -> tuple[bool, str | None]:
    """Whether a Certificate is Ready, and cert-manager's reason if not."""
    if not cert:
        return False, None
    for cond in (cert.get("status") or {}).get("conditions") or []:
        if cond.get("type") == "Ready":
            if cond.get("status") == "True":
                return True, None
            return False, (cond.get("message") or cond.get("reason") or "")[:500]
    return False, None


def _created(obj: dict | None) -> datetime | None:
    raw = ((obj or {}).get("metadata") or {}).get("creationTimestamp")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None


def _wanted() -> list[Domain]:
    """Verified domains of clubs that still exist and aren't suspended."""
    rows = db.session.execute(
        select(Domain, Tenant)
        .join(Tenant, Tenant.id == Domain.tenant_id)
        .where(Domain.verified.is_(True))
    ).all()
    out = []
    for domain, tenant in rows:
        if getattr(tenant, "deleted_at", None) is not None:
            continue
        if (getattr(tenant, "status", None) or "active") in ("suspended", "deleted"):
            continue
        out.append(domain)
    return out


def _alert(domain: Domain) -> None:
    from hubra.core.services import platform_monitor

    platform_monitor.alert(
        "system",
        f"Club domain {domain.domain} has no certificate after a day",
        [
            f"Domain: {domain.domain} (club {domain.tenant_id})",
            f"cert-manager: {domain.serving_error or 'no answer yet'}",
            "Usually the domain doesn't point at the platform yet (CNAME), "
            "or the issuer refused it. It keeps being tried.",
        ],
        level="warning",
        throttle=False,
        link="/app/tenants",
    )


def reconcile() -> dict:
    """Bring the cluster's club-domain objects in line with the database.

    The caller commits. Without a Kubernetes API (Compose, tests) it does
    nothing.
    """
    if not kube.available():
        return {"skipped": "no Kubernetes API"}
    now = _now()
    on = serving_on()
    cfg = _settings()
    selector = f"{LABEL}=true"
    certs = {
        c["metadata"]["name"]: c for c in kube.list_objects("Certificate", selector)
    }
    ings = {i["metadata"]["name"]: i for i in kube.list_objects("Ingress", selector)}
    wanted = _wanted()
    keep: set[str] = set()
    done = {"ready": 0, "pending": 0, "failed": 0, "off": 0, "removed": 0, "errors": 0}

    for domain in wanted:
        name = object_name(domain.domain)
        keep.add(name)
        domain.serving_checked_at = now
        try:
            if not on:
                if name in ings:
                    kube.delete("Ingress", name)
                domain.serving_status = "off"
                domain.serving_since = None
                done["off"] += 1
                continue
            cert = certs.get(name)
            if cert is None or cert.get("spec") != certificate(domain, cfg)["spec"]:
                cert = kube.apply(certificate(domain, cfg))
            ready, why = _ready(cert)
            if ready:
                kube.apply(ingress(domain, cfg))
                if domain.serving_status != "ready":
                    domain.serving_since = now
                domain.serving_status = "ready"
                domain.serving_error = None
                domain.serving_alerted_at = None
                done["ready"] += 1
                continue
            # Not Ready: an Ingress already in place stays (a renewal that
            # fails keeps the old certificate until it runs out).
            domain.serving_error = why
            started = _created(cert) or now
            if now - started > ALERT_AFTER:
                domain.serving_status = "failed"
                if domain.serving_alerted_at is None:
                    domain.serving_alerted_at = now
                    _alert(domain)
                done["failed"] += 1
            else:
                domain.serving_status = "pending"
                done["pending"] += 1
        except kube.KubeError as exc:
            _log.warning("club domain %s: %s", domain.domain, exc)
            domain.serving_error = str(exc)[:500]
            done["errors"] += 1

    # Objects of domains no longer wanted.
    for kind, objs in (("Ingress", ings), ("Certificate", certs)):
        for name in objs:
            if name not in keep:
                try:
                    kube.delete(kind, name)
                    done["removed"] += 1
                except kube.KubeError as exc:
                    _log.warning("club domain object %s: %s", name, exc)
                    done["errors"] += 1
    for domain in db.session.scalars(
        select(Domain).where(
            Domain.verified.is_(False), Domain.serving_status.isnot(None)
        )
    ):
        domain.serving_status = None
        domain.serving_since = None
        domain.serving_error = None
    return done


# ── Visitors ─────────────────────────────────────────────────────────────────

_hosts: dict[str, str] = {}
_hosts_at = 0.0


def _served_hosts() -> dict[str, str]:
    """domain -> club slug for every domain that is served, cached briefly."""
    global _hosts, _hosts_at
    if time.monotonic() - _hosts_at < HOSTS_TTL:
        return _hosts
    try:
        rows = db.session.execute(
            select(Domain.domain, Tenant.slug)
            .join(Tenant, Tenant.id == Domain.tenant_id)
            .where(Domain.verified.is_(True), Domain.serving_status == "ready")
        ).all()
        _hosts = {d.lower(): slug for d, slug in rows}
    except Exception:  # a database hiccup must not break every request
        _log.exception("club domains: could not load the served domains")
        db.session.rollback()
    _hosts_at = time.monotonic()
    return _hosts


def forget_hosts() -> None:
    global _hosts_at
    _hosts_at = 0.0


def destination(host: str, path: str, query: str) -> str | None:
    """Where a request to a club domain goes, or None if *host* isn't one."""
    slug = _served_hosts().get(host.split(":", 1)[0].lower())
    if slug is None:
        return None
    from hubra.core.services.email import _get_base_url

    base = _get_base_url() or ""
    path = path if path and path != "/" else "/app"
    if not path.startswith("/app"):
        path = "/app" + path
    url = f"{base}/{slug}{path}"
    return f"{url}?{query}" if query else url


def install(app: Flask) -> None:
    """Send requests that arrive on a served club domain on to the club."""

    @app.before_request
    def _club_domain():
        host = request.host or ""
        # The platform's own hosts and probes (pod IPs) never match, and
        # cost a dict lookup once the list is loaded.
        if not host or "." not in host:
            return None
        target = destination(host, request.path, request.query_string.decode())
        if target is None:
            return None
        current_app.logger.debug("club domain %s -> %s", host, target)
        return redirect(target, 302)
