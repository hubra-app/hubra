"""Smoke task — verifies the Celery worker can process tasks end-to-end."""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task
def add(x: int | float, y: int | float) -> int | float:
    """Return *x* + *y*.

    Used to verify broker connectivity and worker execution::

        from hubra.core.tasks.smoke import add
        result = add.delay(1, 2)
        assert result.get(timeout=5) == 3
    """
    return x + y
