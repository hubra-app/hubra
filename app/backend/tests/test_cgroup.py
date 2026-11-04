"""Container limits read from cgroup files (hubra.core.cgroup)."""

from __future__ import annotations

import pytest

from hubra.core import cgroup


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(cgroup, "ROOT", str(tmp_path))
    monkeypatch.delenv("CELERY_WORKER_CONCURRENCY", raising=False)
    return tmp_path


def _write(root, path, text):
    f = root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


def test_no_cgroup_files_means_no_limit(root):
    assert cgroup.cpu_limit() is None
    assert cgroup.worker_concurrency(cpu_count=6) is None
    assert cgroup.pressure() == (None, None)


def test_v2_cpu_limit(root):
    _write(root, "cpu.max", "100000 100000\n")
    assert cgroup.cpu_limit() == 1.0
    _write(root, "cpu.max", "max 100000\n")
    assert cgroup.cpu_limit() is None


def test_v1_cpu_limit(root):
    _write(root, "cpu/cpu.cfs_quota_us", "50000\n")
    _write(root, "cpu/cpu.cfs_period_us", "100000\n")
    assert cgroup.cpu_limit() == 0.5
    _write(root, "cpu/cpu.cfs_quota_us", "-1\n")
    assert cgroup.cpu_limit() is None


def test_a_one_cpu_pod_on_a_six_cpu_node_runs_two_children(root):
    """Celery's own default would be six (the node's CPUs)."""
    _write(root, "cpu.max", "100000 100000\n")
    assert cgroup.worker_concurrency(cpu_count=6) == 2
    _write(root, "cpu.max", "250000 100000\n")  # 2.5 CPUs
    assert cgroup.worker_concurrency(cpu_count=16) == 6
    assert cgroup.worker_concurrency(cpu_count=4) == 4  # never above the CPUs


def test_the_env_wins(root, monkeypatch):
    _write(root, "cpu.max", "100000 100000\n")
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "5")
    assert cgroup.worker_concurrency(cpu_count=6) == 5
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "x")
    assert cgroup.worker_concurrency(cpu_count=6) == 2


def test_v2_pressure(root):
    _write(root, "cpu.stat", "usage_usec 9\nnr_throttled 3\nthrottled_usec 1500\n")
    _write(root, "memory.events", "low 0\nhigh 0\nmax 4\noom 0\noom_kill 0\n")
    assert cgroup.pressure() == (1500, 4)


def test_v1_pressure(root):
    _write(root, "cpu/cpu.stat", "nr_periods 10\nnr_throttled 2\nthrottled_time 3000000\n")
    _write(root, "memory/memory.failcnt", "7\n")
    assert cgroup.pressure() == (3000, 7)


def test_held_back():
    p = cgroup.Pressure
    assert cgroup.held_back(p(10, 1), p(10, 1)) == (False, False)
    assert cgroup.held_back(p(10, 1), p(20, 1)) == (True, False)
    assert cgroup.held_back(p(10, 1), p(10, 2)) == (False, True)
    assert cgroup.held_back(p(None, None), p(5, 5)) == (False, False)
    assert cgroup.held_back(None, p(5, 5)) == (False, False)
