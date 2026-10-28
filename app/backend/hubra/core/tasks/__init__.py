"""
Celery task infrastructure for Hubra.

make_celery(app) -- configure a Celery instance bound to a Flask app.
celery_app      -- module-level instance for worker startup.

Worker startup:
    celery -A hubra.core.tasks.celery_app worker --loglevel=info

Inspect active tasks:
    celery -A hubra.core.tasks.celery_app inspect active
"""

from __future__ import annotations

from celery import Celery, Task
from flask import Flask


def make_celery(app: Flask) -> Celery:
    """Create and configure a Celery instance bound to a Flask application.

    Tasks registered against the returned instance will execute inside a
    Flask application context so ``db``, ``current_app``, etc. are available.

    Args:
        app: A fully configured Flask application.

    Returns:
        A configured :class:`~celery.Celery` instance stored at
        ``app.extensions["celery"]``.
    """

    class FlaskTask(Task):
        """Task subclass that pushes a Flask app context before each execution.

        A task queued during a request for a club carries that club's id in
        a ``tenant_id`` header, and runs with the club's schema and
        ``g.tenant`` set, so it reads and writes the same data the request
        did.
        """

        def apply_async(self, args=None, kwargs=None, **options):
            from hubra.core.tenant.context import current_tenant

            try:
                tenant = current_tenant()
            except RuntimeError:  # no app context
                tenant = None
            if tenant is not None:
                headers = dict(options.get("headers") or {})
                headers.setdefault("tenant_id", tenant.id)
                options["headers"] = headers
            return super().apply_async(args, kwargs, **options)

        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                tenant_id = getattr(self.request, "tenant_id", None) or (
                    getattr(self.request, "headers", None) or {}
                ).get("tenant_id")
                if tenant_id is None:
                    return self.run(*args, **kwargs)

                from flask import g

                from hubra.core.extensions import db
                from hubra.core.models.tenant import Tenant
                from hubra.core.tenant.context import (
                    reset_search_path,
                    set_search_path,
                )

                g.tenant = db.session.get(Tenant, int(tenant_id))
                set_search_path(int(tenant_id))
                try:
                    return self.run(*args, **kwargs)
                finally:
                    # A failed task leaves the transaction aborted; SET
                    # search_path would then fail and hide the real error.
                    db.session.rollback()
                    reset_search_path()
                    g.tenant = None

    testing = app.config.get("TESTING", False)
    broker = (
        "memory://"
        if testing
        else (app.config.get("REDIS_URL") or "redis://localhost:6379/0")
    )

    from celery.schedules import crontab

    instance = Celery(
        app.name,
        task_cls=FlaskTask,
        include=[
            "hubra.core.tasks.wildduck",
            "hubra.core.tasks.email_tasks",
            "hubra.core.tasks.finance_tasks",
            "hubra.core.tasks.mail_tasks",
            "hubra.core.tasks.mail_sync",
            "hubra.core.tasks.session_tasks",
            "hubra.core.tasks.health_tasks",
            "hubra.core.tasks.i18n_tasks",
            "hubra.core.tasks.backup_tasks",
            "hubra.core.tasks.domain_tasks",
            "hubra.core.tasks.monitoring",
            "hubra.core.tasks.infra_checks",
            "hubra.core.tasks.plugin_tasks",
            *_module_task_imports(),
        ],
    )
    conf: dict = dict(
        broker_url=broker,
        result_backend="cache+memory://" if testing else broker,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        beat_schedule={
            "generate-invoices-daily": {
                "task": "hubra.core.tasks.finance_tasks.generate_invoices_task",
                "schedule": crontab(hour=8, minute=0),
            },
            "send-overdue-reminders-daily": {
                "task": "hubra.core.tasks.finance_tasks.send_overdue_reminders_task",
                "schedule": crontab(hour=9, minute=0),
            },
            "retention-cleanup-daily": {
                "task": "hubra.core.tasks.mail_tasks.retention_cleanup",
                "schedule": crontab(hour=2, minute=0),
            },
            "cleanup-token-blocklist-daily": {
                "task": "hubra.core.tasks.mail_tasks.cleanup_token_blocklist",
                "schedule": crontab(hour=3, minute=0),
            },
            "sync-wildduck-message-counts": {
                "task": "hubra.core.tasks.mail_sync.sync_wildduck_message_counts",
                "schedule": 60.0,
            },
            "sync-wildduck-quota-5min": {
                "task": "hubra.core.tasks.mail_sync.sync_wildduck_quota",
                "schedule": crontab(minute="*/5"),
            },
            "cleanup-revoked-sessions-weekly": {
                "task": "hubra.core.tasks.session_tasks.cleanup_revoked_sessions",
                "schedule": crontab(hour=3, minute=0, day_of_week=0),
            },
            "mail-reconcile-v2-15min": {
                "task": "hubra.core.tasks.mail_tasks.reconcile_mail",
                "schedule": crontab(minute="*/15"),
            },
            "check-mailbox-quota-hourly": {
                "task": "hubra.core.tasks.mail_tasks.check_mailbox_quota",
                "schedule": crontab(minute=5),
            },
            "health-check-20s": {
                "task": "hubra.core.tasks.health_tasks.run_health_checks",
                "schedule": 20.0,
            },
            "backup-daily": {
                "task": "hubra.core.tasks.backup_tasks.create_scheduled_backups",
                "schedule": crontab(hour=3, minute=0),
                "kwargs": {
                    "backup_type": "scheduled_daily",
                    "triggered_by": "schedule",
                },
            },
            "backup-weekly": {
                "task": "hubra.core.tasks.backup_tasks.create_scheduled_backups",
                "schedule": crontab(hour=3, minute=15, day_of_week=0),
                "kwargs": {
                    "backup_type": "scheduled_weekly",
                    "triggered_by": "schedule",
                },
            },
            "backup-monthly": {
                "task": "hubra.core.tasks.backup_tasks.create_scheduled_backups",
                "schedule": crontab(hour=3, minute=30, day_of_month=1),
                "kwargs": {
                    "backup_type": "scheduled_monthly",
                    "triggered_by": "schedule",
                },
            },
            # ── M7: Monitoring checks ──────────────────────────────────────
            "infra-checks-hourly": {
                "task": "hubra.core.tasks.infra_checks.run_all_checks_task",
                "schedule": crontab(minute=0),
            },
            "api-error-rate-hourly": {
                "task": "hubra.core.tasks.monitoring.check_api_error_rate_task",
                "schedule": crontab(minute=15),
            },
            "plugin-updates": {
                "task": "hubra.core.tasks.plugin_tasks.check_plugin_updates",
                "schedule": crontab(hour="*/6", minute=40),
            },
        },
        broker_connection_retry_on_startup=False,
        timezone="UTC",
    )
    conf["beat_schedule"].update(_module_schedules())
    if testing:
        conf["task_always_eager"] = True
        conf["task_eager_propagates"] = True
    instance.conf.update(conf)
    instance.set_default()
    app.extensions["celery"] = instance
    instance.flask_app = app
    return instance


def _module_task_imports() -> list[str]:
    """Celery task modules declared by module manifests (``tasks=``)."""
    from hubra.core.modules import registry

    registry.load()
    return registry.task_modules()


def _module_schedules() -> dict:
    """Periodic tasks declared by module manifests (``schedule=``)."""
    from hubra.core.modules import registry

    registry.load()
    return {s.name: {"task": s.task, "schedule": s.every} for s in registry.schedules()}


def _bootstrap_celery() -> Celery:
    """Bootstrap Celery with a default Flask app for worker process startup.

    Called once at module import time so ``celery -A hubra.core.tasks`` works.
    """
    from hubra import create_app  # noqa: PLC0415 -- deferred to avoid circular

    return make_celery(create_app())


celery_app = _bootstrap_celery()


def _watch_plugins(**_kwargs) -> None:
    """Stop gracefully when plugins change, so the container restarts with them."""
    from hubra.core.plugins.reload import watch_celery

    watch_celery()


from celery import signals  # noqa: E402


def _fresh_db_connections(**_kwargs) -> None:
    """Give each forked worker process its own database connections.

    The app is created (and the pool filled) in the parent before the
    prefork pool forks; children sharing those sockets interleave their
    queries ("error with status PGRES_TUPLES_OK and no message").
    """
    from hubra.core.extensions import db

    with celery_app.flask_app.app_context():
        db.engine.dispose(close=False)


signals.worker_process_init.connect(_fresh_db_connections, weak=False)
signals.worker_ready.connect(_watch_plugins, weak=False)
signals.beat_init.connect(_watch_plugins, weak=False)
