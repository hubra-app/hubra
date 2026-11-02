"""Celery signals that feed the background job dashboard
(``hubra.core.services.job_monitor``).  Imported by ``hubra.core.tasks`` so
every process that sends or runs jobs (web, beat, worker) records them."""

from __future__ import annotations

from celery import signals

from hubra.core.services import job_monitor


def _name(sender) -> str:
    return getattr(sender, "name", None) or str(sender)


def _tenant_id(task) -> int | None:
    request = getattr(task, "request", None)
    value = getattr(request, "tenant_id", None) or (
        getattr(request, "headers", None) or {}
    ).get("tenant_id")
    return value


@signals.before_task_publish.connect(weak=False)
def _sent(sender=None, headers=None, **_kw):
    job_monitor.count(str((headers or {}).get("task") or sender), "sent")


@signals.task_prerun.connect(weak=False)
def _prerun(sender=None, task_id=None, task=None, **_kw):
    job_monitor.started(str(task_id), _name(task or sender), _tenant_id(task))


@signals.task_postrun.connect(weak=False)
def _postrun(sender=None, task_id=None, task=None, state=None, **_kw):
    ms = job_monitor.finished(str(task_id))
    if state == "SUCCESS":
        job_monitor.count(_name(task or sender), "done", ms)


@signals.task_retry.connect(weak=False)
def _retry(sender=None, request=None, **_kw):
    job_monitor.count(_name(sender), "retried")


@signals.task_failure.connect(weak=False)
def _failure(
    sender=None, task_id=None, exception=None, args=None, kwargs=None, einfo=None, **_kw
):
    name = _name(sender)
    job_monitor.count(name, "failed")
    job_monitor.failed(
        task_id=str(task_id),
        task=name,
        args=args,
        kwargs=kwargs,
        exception=exception,
        einfo=einfo,
        tenant_id=_tenant_id(sender),
        retries=getattr(getattr(sender, "request", None), "retries", 0),
    )
