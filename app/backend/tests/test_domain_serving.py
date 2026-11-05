"""Club domains: certificate first, then Ingress; the kill switch; leftovers
removed; visitors redirected. The Kubernetes API is a small fake."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from hubra.core import kube
from hubra.core.models.domain import Domain
from hubra.core.models.tenant import Tenant
from hubra.core.services import domain_serving, platform_settings


class FakeKube:
    def __init__(self):
        self.objects: dict[tuple[str, str], dict] = {}
        self.ready: set[str] = set()
        self.calls: list[tuple[str, str]] = []

    def _status(self, obj):
        """What cert-manager would report by now."""
        status = "True" if obj["metadata"]["name"] in self.ready else "False"
        obj["status"] = {
            "conditions": [{"type": "Ready", "status": status, "message": "Issuing"}]
        }

    def __call__(self, method, url, headers, body):
        u = urlparse(url)
        parts = u.path.split("/")
        plural = parts[parts.index("namespaces") + 2]
        kind = {"ingresses": "Ingress", "certificates": "Certificate"}[plural]
        name = (
            parts[parts.index("namespaces") + 3]
            if len(parts) > parts.index("namespaces") + 3
            else None
        )
        self.calls.append((method, f"{kind}/{name or ''}"))
        assert headers["Authorization"] == "Bearer tok"
        if method == "GET":
            sel = parse_qs(u.query)["labelSelector"][0].split("=")[0]
            items = [
                o
                for (k, _), o in self.objects.items()
                if k == kind and sel in o["metadata"].get("labels", {})
            ]
            for o in items:
                if kind == "Certificate":
                    self._status(o)
            return 200, json.dumps({"items": items}).encode()
        if method == "PATCH":
            assert headers["Content-Type"] == "application/apply-patch+yaml"
            obj = json.loads(body)
            obj["metadata"]["creationTimestamp"] = (
                self.objects.get((kind, name), {})
                .get("metadata", {})
                .get("creationTimestamp")
                or datetime.now(timezone.utc).isoformat()
            )
            if kind == "Certificate":
                self._status(obj)
            self.objects[(kind, name)] = obj
            return 200, json.dumps(obj).encode()
        if method == "DELETE":
            if self.objects.pop((kind, name), None) is None:
                return 404, b'{"message": "not found"}'
            return 200, b"{}"
        return 405, b"{}"


@pytest.fixture
def k8s(monkeypatch, tmp_path):
    (tmp_path / "token").write_text("tok")
    (tmp_path / "namespace").write_text("hubra")
    monkeypatch.setattr(kube, "SA_DIR", str(tmp_path))
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    fake = FakeKube()
    monkeypatch.setattr(kube, "_send", fake)
    domain_serving.forget_hosts()
    yield fake
    domain_serving.forget_hosts()


@pytest.fixture
def club_domain(app, db):
    tenant = Tenant(name="FC Domain", slug="fc-domain", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    d = Domain(
        tenant_id=tenant.id,
        domain="mitglieder.fc-domain.ch",
        verified=True,
        verification_status="verified",
        verified_at=datetime.now(timezone.utc),
    )
    db.session.add(d)
    platform_settings.set_many({"domains.serving": "on"})
    db.session.commit()
    return d


def test_nothing_happens_outside_a_cluster(app, db, club_domain, monkeypatch):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    assert domain_serving.reconcile() == {"skipped": "no Kubernetes API"}


def test_certificate_first_then_ingress(app, db, club_domain, k8s):
    name = domain_serving.object_name(club_domain.domain)
    done = domain_serving.reconcile()
    db.session.commit()
    assert done["pending"] == 1
    assert ("Certificate", name) in k8s.objects
    assert ("Ingress", name) not in k8s.objects
    cert = k8s.objects[("Certificate", name)]
    assert cert["spec"]["dnsNames"] == ["mitglieder.fc-domain.ch"]
    assert cert["spec"]["issuerRef"] == {"name": "letsencrypt", "kind": "ClusterIssuer"}
    assert club_domain.serving_status == "pending"
    assert club_domain.serving_error == "Issuing"

    k8s.ready.add(name)
    domain_serving.reconcile()
    db.session.commit()
    ing = k8s.objects[("Ingress", name)]
    rule = ing["spec"]["rules"][0]
    assert rule["host"] == "mitglieder.fc-domain.ch"
    assert rule["http"]["paths"][0]["backend"]["service"]["name"] == "global-backend"
    assert ing["spec"]["tls"][0]["secretName"] == f"{name}-tls"
    assert ing["metadata"]["labels"][domain_serving.LABEL] == "true"
    assert club_domain.serving_status == "ready" and club_domain.serving_since


def test_kill_switch_removes_ingresses_only(app, db, club_domain, k8s):
    name = domain_serving.object_name(club_domain.domain)
    k8s.ready.add(name)
    domain_serving.reconcile()
    domain_serving.reconcile()
    assert ("Ingress", name) in k8s.objects
    platform_settings.set_many({"domains.serving": "off"})
    db.session.commit()
    domain_serving.reconcile()
    db.session.commit()
    assert ("Ingress", name) not in k8s.objects
    assert ("Certificate", name) in k8s.objects
    assert club_domain.serving_status == "off"


def test_unverified_or_deleted_domains_lose_their_objects(app, db, club_domain, k8s):
    name = domain_serving.object_name(club_domain.domain)
    k8s.ready.add(name)
    domain_serving.reconcile()
    domain_serving.reconcile()
    # Somebody's own Ingress without the label is never touched.
    k8s.objects[("Ingress", "hand-made")] = {
        "metadata": {"name": "hand-made", "labels": {}}
    }
    club_domain.verified = False
    db.session.commit()
    done = domain_serving.reconcile()
    db.session.commit()
    assert done["removed"] == 2
    assert set(k8s.objects) == {("Ingress", "hand-made")}
    assert club_domain.serving_status is None


def test_alert_after_a_day_without_certificate(app, db, club_domain, k8s, monkeypatch):
    from hubra.core.services import platform_monitor

    sent = []
    monkeypatch.setattr(
        platform_monitor, "alert", lambda *a, **kw: sent.append(a) or True
    )
    name = domain_serving.object_name(club_domain.domain)
    domain_serving.reconcile()
    k8s.objects[("Certificate", name)]["metadata"]["creationTimestamp"] = (
        datetime.now(timezone.utc) - timedelta(hours=25)
    ).isoformat()
    domain_serving.reconcile()
    domain_serving.reconcile()
    db.session.commit()
    assert club_domain.serving_status == "failed"
    assert len(sent) == 1 and "mitglieder.fc-domain.ch" in sent[0][1]


def test_visitors_are_sent_to_the_club(app, db, client, club_domain, k8s):
    app.config["FRONTEND_BASE_URL"] = "https://app.hubra.club"
    k8s.ready.add(domain_serving.object_name(club_domain.domain))
    domain_serving.reconcile()
    domain_serving.reconcile()
    db.session.commit()
    domain_serving.forget_hosts()

    r = client.get("/", headers={"Host": "mitglieder.fc-domain.ch"})
    assert r.status_code == 302
    assert r.headers["Location"] == "https://app.hubra.club/fc-domain/app"
    r = client.get("/events?x=1", headers={"Host": "Mitglieder.FC-Domain.ch"})
    assert r.headers["Location"] == "https://app.hubra.club/fc-domain/app/events?x=1"
    # Other hosts go on as before.
    assert client.get("/health", headers={"Host": "api.hubra.club"}).status_code == 200


def test_domain_list_shows_serving_and_cname(app, db, club_domain, k8s):
    from hubra.api.admin.routes import _domain_to_dict

    platform_settings.set_many({"domains.cname_target": "clubs.hubra.club"})
    db.session.commit()
    out = _domain_to_dict(club_domain)
    assert out["cname_target"] == "clubs.hubra.club"
    platform_settings.set_many({"domains.serving": "off"})
    db.session.commit()
    assert _domain_to_dict(club_domain)["cname_target"] is None
