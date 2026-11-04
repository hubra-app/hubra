"""What the container limits this process to, and how often it hit them.

Read from the cgroup files a container sees (v2 at ``/sys/fs/cgroup``, v1
under ``/sys/fs/cgroup/<controller>``).  Everything returns None outside a
container or when a file is missing, never raises.

* ``cpu_limit()``: the CPU limit in CPUs (``limits.cpu`` of the pod).
* ``pressure()``: counters that only grow: microseconds the cgroup was
  throttled for using up its CPU quota, and how often it reached its
  memory limit (the kernel then reclaims memory before it goes on).  The
  difference between two readings says whether the process was held back
  in between, which a slow statement's own time cannot show.
"""

from __future__ import annotations

import math
import os
from typing import NamedTuple

ROOT = "/sys/fs/cgroup"


def _read(*parts: str) -> str | None:
    try:
        with open(os.path.join(ROOT, *parts), encoding="ascii") as f:
            return f.read()
    except (OSError, ValueError):
        return None


def _fields(text: str | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in (text or "").splitlines():
        name, _, value = line.partition(" ")
        try:
            out[name] = int(value.split()[0])
        except (ValueError, IndexError):
            continue
    return out


def cpu_limit() -> float | None:
    """The CPU quota in CPUs, or None when there is none."""
    raw = _read("cpu.max")  # v2: "<quota|max> <period>"
    if raw is not None:
        quota, _, period = raw.strip().partition(" ")
        if quota == "max":
            return None
        try:
            return int(quota) / int(period)
        except (ValueError, ZeroDivisionError):
            return None
    for ctl in ("cpu", "cpu,cpuacct"):  # v1
        quota = _read(ctl, "cpu.cfs_quota_us")
        period = _read(ctl, "cpu.cfs_period_us")
        if quota is not None and period is not None:
            try:
                q, p = int(quota), int(period)
            except ValueError:
                return None
            return q / p if q > 0 and p > 0 else None
    return None


def worker_concurrency(cpu_count: int | None = None) -> int | None:
    """How many prefork children a Celery worker should run, or None to
    keep Celery's default (one per CPU of the machine).

    ``CELERY_WORKER_CONCURRENCY`` wins.  Otherwise, under a CPU limit, two
    per CPU of the limit (at least two): Celery counts the node's CPUs, not
    the pod's, so a 1-CPU worker on a 6-CPU node ran six children that took
    turns on one CPU and did not fit in 512 MiB.
    """
    raw = os.environ.get("CELERY_WORKER_CONCURRENCY", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    limit = cpu_limit()
    if limit is None:
        return None
    wanted = max(2, 2 * math.ceil(limit))
    cpus = cpu_count if cpu_count is not None else os.cpu_count()
    return min(wanted, cpus) if cpus else wanted


class Pressure(NamedTuple):
    throttled_us: int | None
    memory_limit_hits: int | None


def pressure() -> Pressure:
    """The cgroup's throttling and memory-limit counters (see module doc)."""
    stat = _fields(_read("cpu.stat"))
    if "throttled_usec" in stat:  # v2
        throttled: int | None = stat["throttled_usec"]
    else:
        v1 = _fields(_read("cpu", "cpu.stat")) or _fields(_read("cpu,cpuacct", "cpu.stat"))
        throttled = v1["throttled_time"] // 1000 if "throttled_time" in v1 else None
    events = _fields(_read("memory.events"))  # v2
    if "max" in events:
        hits: int | None = events["max"]
    else:
        raw = _read("memory", "memory.failcnt")  # v1
        try:
            hits = int(raw) if raw is not None else None
        except ValueError:
            hits = None
    return Pressure(throttled, hits)


def held_back(before: Pressure | None, after: Pressure | None) -> tuple[bool, bool]:
    """``(cpu, memory)``: whether the cgroup was throttled, or reached its
    memory limit, between the two readings."""
    if before is None or after is None:
        return False, False

    def grew(a, b) -> bool:
        return a is not None and b is not None and b > a

    return (
        grew(before.throttled_us, after.throttled_us),
        grew(before.memory_limit_hits, after.memory_limit_hits),
    )
