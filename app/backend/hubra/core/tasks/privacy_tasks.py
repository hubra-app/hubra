"""Daily job: delete former members after the club's retention period.

A club that sets Settings › Club › "Delete former members after N years"
(``former_member_retention_years``, off by default) has members who left
more than N years ago deleted once a day. See
``hubra.core.services.data_requests.purge_former_members``.
"""

from __future__ import annotations

import logging

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="hubra.core.tasks.privacy_tasks.purge_former_members_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def purge_former_members_task(self) -> dict:
    """Former members past the retention period, in every club."""
    return _purge_former_members()


@per_tenant_job("members")
def _purge_former_members() -> dict:
    from hubra.core.services.data_requests import purge_former_members
    from hubra.core.services.privacy import retention_years
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    years = retention_years(tenant)
    if tenant is None or years is None:
        return {"skipped": "no retention period"}
    result = purge_former_members(tenant, years)
    if result["deleted"] or result["skipped"]:
        logger.info("privacy retention: %s", result)
    return result
