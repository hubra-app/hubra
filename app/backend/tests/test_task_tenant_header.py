"""A job queued for a club runs in that club, and never anywhere else."""

from __future__ import annotations

from flask import g

from hubra.core.tasks import celery_app


@celery_app.task(name="tests.task_tenant_header.where_am_i")
def where_am_i():
    tenant = getattr(g, "tenant", None)
    return tenant.id if tenant is not None else "no-club"


def _run(headers=None):
    # The tenant part of the task's __call__, inside the test app (the
    # module-level Celery app has its own Flask app and database).
    where_am_i.push_request(headers=headers or {})
    try:
        return where_am_i._run_in_tenant()
    finally:
        where_am_i.pop_request()


def test_job_runs_in_its_club(app, db, tenant_pair):
    tenant_id = tenant_pair["tenant_a"].id
    assert _run({"tenant_id": tenant_id}) == tenant_id


def test_job_of_a_deleted_club_is_dropped(app, db, tenant_pair):
    # The club is gone: running the job without it (in public) would act
    # on the wrong data, so it doesn't run at all.
    assert _run({"tenant_id": 999_999}) is None


def test_job_without_a_club_runs_outside_any(app, db):
    assert _run() == "no-club"
