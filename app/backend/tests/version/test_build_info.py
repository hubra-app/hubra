"""The commit each process was built from (hubra.core.build_info)."""

import json

from hubra.core import build_info


class _FakeRedis:
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def set(self, key, value, ex=None):
        self.data[key] = value.encode() if isinstance(value, str) else value

    def get(self, key):
        return self.data.get(key.decode() if isinstance(key, bytes) else key)

    def scan_iter(self, match, count=100):
        prefix = match.rstrip("*")
        return [k.encode() for k in self.data if k.startswith(prefix)]


def test_commit_is_none_without_env(monkeypatch):
    monkeypatch.delenv("HUBRA_GIT_SHA", raising=False)
    assert build_info.commit() is None
    monkeypatch.setenv("HUBRA_GIT_SHA", "  ")
    assert build_info.commit() is None


def test_commit_from_env(monkeypatch):
    monkeypatch.setenv("HUBRA_GIT_SHA", "abc123def456")
    assert build_info.commit() == "abc123def456"


def test_report_and_read_back(app, monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("hubra.core.redis_client.get_redis_client", lambda *a, **k: fake)
    monkeypatch.setenv("HUBRA_GIT_SHA", "feedface")
    monkeypatch.setenv("HOSTNAME", "worker-abc")
    with app.app_context():
        build_info._write("worker")
        fake.data["hubra:build:broken"] = b"not json"
        reported = build_info.reported()
    assert len(reported) == 1
    assert reported[0]["component"] == "worker"
    assert reported[0]["host"] == "worker-abc"
    assert reported[0]["commit"] == "feedface"
    assert reported[0]["version"]
    assert json.loads(fake.data["hubra:build:worker:worker-abc"])["seen"] > 0


def test_reported_is_empty_without_redis(app, monkeypatch):
    monkeypatch.setattr("hubra.core.redis_client.get_redis_client", lambda *a, **k: None)
    with app.app_context():
        assert build_info.reported() == []


def test_version_endpoint_has_commit(client, monkeypatch):
    monkeypatch.setenv("HUBRA_GIT_SHA", "0123456789abcdef")
    data = client.get("/api/v1/version").get_json()
    assert data["commit"] == "0123456789abcdef"
    monkeypatch.delenv("HUBRA_GIT_SHA")
    assert client.get("/api/v1/version").get_json()["commit"] is None


def test_platform_health_has_commits(client, staff_headers, monkeypatch):
    monkeypatch.setenv("HUBRA_GIT_SHA", "0123456789abcdef")
    data = client.get("/api/v1/manager/platform/health", headers=staff_headers).get_json()
    assert data["commit"] == "0123456789abcdef"
    assert isinstance(data["processes"], list)
    assert "last_upgrade" in data
