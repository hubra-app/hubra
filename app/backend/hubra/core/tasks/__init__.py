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

from . import scheduling


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
            from hubra.core import request_id

            headers = dict(options.get("headers") or {})
            if tenant is not None:
                headers.setdefault("tenant_id", tenant.id)
            rid = request_id.current()
            if rid:
                # The task's log lines carry the id of what started it.
                headers.setdefault("request_id", rid)
            if headers:
                options["headers"] = headers
            return super().apply_async(args, kwargs, **options)

        def _header(self, name: str):
            return getattr(self.request, name, None) or (
                getattr(self.request, "headers", None) or {}
            ).get(name)

        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                # The slow-query threshold (read at most once a minute).
                from hubra.core.services.perf_monitor import (
                    mark_start,
                    refresh_thresholds,
                )

                refresh_thresholds()
                # Slow queries of this task say if the pod was held back.
                mark_start()
                from flask import g

                from hubra.core import request_id

                g.request_id = request_id.accept(self._header("request_id"))
                job = self._header(scheduling.HEADER)
                if job:
                    # Sent by beat: one run of this schedule entry at a time,
                    # however many workers there are.
                    return scheduling.run_exclusive(
                        job, self._run_in_tenant, *args, **kwargs
                    )
                return self._run_in_tenant(*args, **kwargs)

        def _run_in_tenant(self, *args: object, **kwargs: object) -> object:
            tenant_id = self._header("tenant_id")
            if tenant_id is None:
                return self.run(*args, **kwargs)

            from flask import g

            from hubra.core.extensions import db
            from hubra.core.models.tenant import Tenant
            from hubra.core.tenant.context import (
                reset_search_path,
                set_search_path,
            )

            tenant = db.session.get(Tenant, int(tenant_id))
            if tenant is None:
                # The club is gone (deleted after the job was queued). Its
                # schema is gone too, and Postgres skips a missing schema in
                # search_path, so the job would read and write public
                # instead. Drop it rather than run it anywhere else.
                import logging

                logging.getLogger(__name__).warning(
                    "task %s dropped: club %s no longer exists",
                    self.name,
                    tenant_id,
                )
                return None
            g.tenant = tenant
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
            "hubra.core.tasks.platform_discord_tasks",
            "hubra.core.tasks.platform_bot_tasks",
            "hubra.core.tasks.support_discord_tasks",
            "hubra.core.tasks.push_tasks",
            "hubra.core.tasks.mail_monitor_tasks",
            "hubra.core.tasks.connected_app_tasks",
            "hubra.core.tasks.plugin_event_tasks",
            "hubra.core.tasks.contract_tasks",
            "hubra.core.tasks.quota_tasks",
            "hubra.core.tasks.upgrade_tasks",
            "hubra.core.tasks.post_deploy_tasks",
            "hubra.core.tasks.billing_tasks",
            "hubra.core.tasks.wallet_tasks",
            *_module_task_imports(),
        ],
    )
    conf: dict = {
        "broker_url": broker,
        "result_backend": "cache+memory://" if testing else broker,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "beat_schedule": {
            "generate-invoices-daily": {
                "task": "hubra.core.tasks.finance_tasks.generate_invoices_task",
                "schedule": crontab(hour=8, minute=0),
            },
            "send-overdue-reminders-daily": {
                "task": "hubra.core.tasks.finance_tasks.send_overdue_reminders_task",
                "schedule": crontab(hour=9, minute=0),
            },
            "fee-adjustment-reminders-daily": {
                "task": "hubra.core.tasks.finance_tasks.fee_adjustment_reminders_task",
                "schedule": crontab(hour=9, minute=10),
            },
            "retention-cleanup-daily": {
                "task": "hubra.core.tasks.mail_tasks.retention_cleanup",
                "schedule": crontab(hour=2, minute=0),
            },
            "cleanup-token-blocklist-daily": {
                "task": "hubra.core.tasks.mail_tasks.cleanup_token_blocklist",
                "schedule": crontab(hour=3, minute=0),
            },
            "verify-protected-mail-daily": {
                "task": "hubra.core.tasks.mail_tasks.verify_protected_mail_addresses",
                "schedule": crontab(hour=4, minute=0),
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
            # Every 10 minutes over the last hour; one alert per incident.
            "api-error-rate-10min": {
                "task": "hubra.core.tasks.monitoring.check_api_error_rate_task",
                "schedule": 600.0,
            },
            "check-domains-every-minute": {
                "task": "hubra.core.tasks.domain_tasks.check_domains",
                "schedule": 60.0,
            },
            # Club domains: certificate, then Ingress (no-op outside Kubernetes).
            "serve-domains-2min": {
                "task": "hubra.core.tasks.domain_tasks.serve_domains",
                "schedule": 120.0,
            },
            "check-mail-relays-5min": {
                "task": "hubra.core.tasks.mail_monitor_tasks.check_mail_relays",
                "schedule": crontab(minute="*/5"),
            },
            "prune-platform-events-daily": {
                "task": "hubra.core.tasks.mail_monitor_tasks.prune_platform_events",
                "schedule": crontab(hour=2, minute=30),
            },
            "discord-role-connections-nightly": {
                "task": "hubra.core.tasks.connected_app_tasks.push_all_role_connections",
                "schedule": crontab(hour=4, minute=10),
            },
            # Cached answers for manage's slow status pages (S3, Discord).
            "check-backup-config-5min": {
                "task": "hubra.core.tasks.backup_tasks.check_backup_config",
                "schedule": 300.0,
            },
            "check-discord-bot-4min": {
                "task": "hubra.core.tasks.platform_discord_tasks.check_discord_bot",
                "schedule": 240.0,
            },
            # A new build rolling out, and when every process runs it.
            "check-upgrades-every-minute": {
                "task": "hubra.core.tasks.upgrade_tasks.check_upgrades",
                "schedule": 60.0,
            },
            # Planned maintenance, resolved alerts, releases, 08:00 digest.
            "platform-bot-every-minute": {
                "task": "hubra.core.tasks.platform_bot_tasks.tick",
                "schedule": 60.0,
            },
            # Plugin events and queued actions: retries, and rows the
            # transport lost (hubra.core.contracts.outbox).
            "contract-outbox-every-minute": {
                "task": "hubra.core.tasks.contract_tasks.sweep",
                "schedule": 60.0,
            },
            "plugin-updates": {
                "task": "hubra.core.tasks.plugin_tasks.check_plugin_updates",
                "schedule": crontab(hour="*/6", minute=40),
            },
            # Club limits: warn owners at limits.warn_percent and at 100 %.
            "check-club-limits-hourly": {
                "task": "hubra.core.tasks.quota_tasks.check_quotas",
                "schedule": crontab(minute=25),
            },
            # Club subscriptions: Stripe's state, in case a webhook got lost.
            "reconcile-billing-hourly": {
                "task": "hubra.core.tasks.billing_tasks.reconcile_billing",
                "schedule": crontab(minute=35),
            },
            # Google Wallet passes of the member badge whose content changed
            # without an event (a club renamed); unchanged ones cost nothing.
            "google-wallet-passes-nightly": {
                "task": "hubra.core.tasks.wallet_tasks.refresh_google_wallet_passes",
                "schedule": crontab(hour=3, minute=50),
            },
        },
        "broker_connection_retry_on_startup": False,
        "timezone": "UTC",
        **worker_defaults(),
        # One send per schedule slot even with several beats; see scheduling.py.
        "beat_scheduler": "hubra.core.tasks.scheduling:HubraScheduler",
    }
    conf["beat_schedule"].update(_module_schedules())
    # Platform tasks on their own queue when a platform worker runs them
    # (HUBRA_PLATFORM_QUEUE; hubra.core.roles).
    from hubra.core.roles import task_routes

    conf["task_routes"] = task_routes()
    # Children per worker from the pod's CPU limit, not the node's CPUs
    # (CELERY_WORKER_CONCURRENCY or --concurrency still win; see cgroup.py).
    from hubra.core.cgroup import worker_concurrency

    children = worker_concurrency()
    if children is not None:
        conf["worker_concurrency"] = children
    if testing:
        conf["task_always_eager"] = True
        conf["task_eager_propagates"] = True
    instance.conf.update(conf)
    instance.set_default()
    app.extensions["celery"] = instance
    instance.flask_app = app
    return instance


def _env_int(name: str, default: int) -> int:
    import os

    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def worker_defaults() -> dict:
    """Celery settings every task gets unless it says otherwise.

    - **Time limits.** A task gets ``SoftTimeLimitExceeded`` after
      ``CELERY_TASK_SOFT_TIME_LIMIT`` seconds (15 min) and is killed a minute
      later, so a hung network call or query can't hold a worker child (and,
      for a scheduled job, its advisory lock) for hours. Long jobs (backups,
      restores) set their own limits; short checks set tighter ones.
    - **Late acks.** A task's message is acknowledged when it finishes, so a
      worker that is stopped mid-task (a deploy, a restart) hands it to the
      next one. Tasks must therefore be safe to run twice; the few that
      aren't (and the long ones, see the visibility timeout) set
      ``acks_late=False``.
    - **One message at a time per child** (prefetch 1): a long task doesn't
      sit on short ones that another child could run.
    - **No results** unless a task asks for them: nothing in Hubra reads
      them, and they filled Redis for a day each.
    - **Children are recycled** after ``CELERY_MAX_TASKS_PER_CHILD`` tasks
      (500) or when they grow past ``CELERY_MAX_MEMORY_PER_CHILD`` KiB
      (250 000), so a leak can't push the pod over its memory limit.
    - **Visibility timeout** two hours: Redis hands an unacknowledged
      message to another worker after this long, so it must be longer than
      any late-acked task and any ``countdown`` (webhook retries wait up to
      an hour).
    """
    soft = _env_int("CELERY_TASK_SOFT_TIME_LIMIT", 15 * 60)
    return {
        "task_soft_time_limit": soft,
        "task_time_limit": soft + 60,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "worker_cancel_long_running_tasks_on_connection_loss": True,
        "task_ignore_result": True,
        "result_expires": 3600,
        "worker_max_tasks_per_child": _env_int("CELERY_MAX_TASKS_PER_CHILD", 500),
        "worker_max_memory_per_child": _env_int("CELERY_MAX_MEMORY_PER_CHILD", 250_000),
        "broker_transport_options": {"visibility_timeout": VISIBILITY_TIMEOUT},
        "result_backend_transport_options": {"visibility_timeout": VISIBILITY_TIMEOUT},
    }


# Longer than any late-acked task and any countdown (see worker_defaults).
VISIBILITY_TIMEOUT = 2 * 3600


def _module_task_imports(plugins: bool = False) -> list[str]:
    """Celery task modules declared by module manifests (``tasks=``): those
    of Hubra's own modules, or with *plugins* those of plugins."""
    from hubra.core.modules import registry

    registry.load()
    out: list[str] = []
    for m in registry.all():
        if bool(m.plugin) == plugins:
            out.extend(t for t in m.tasks if t not in out)
    return out


def _import_plugin_task_modules(**_kwargs) -> list[str]:
    """Import plugins' task modules once the worker (or beat) has started,
    each on its own: one that fails is logged and its tasks are missing,
    instead of the worker not starting (tasks.include raises). Returns the
    modules that failed."""
    import importlib
    import logging

    failed = []
    for name in _module_task_imports(plugins=True):
        try:
            importlib.import_module(name)
        except Exception:
            logging.getLogger(__name__).exception(
                "Plugin task module %s failed to import; its tasks won't run", name
            )
            failed.append(name)
    return failed


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
    from hubra.core import db_limits
    from hubra.core.extensions import db

    with celery_app.flask_app.app_context():
        # Its own connections, with the worker's statement and idle limits.
        db_limits.use("worker", db.engine)


signals.import_modules.connect(_import_plugin_task_modules, weak=False)
signals.worker_process_init.connect(_fresh_db_connections, weak=False)
signals.worker_ready.connect(_watch_plugins, weak=False)
signals.beat_init.connect(_watch_plugins, weak=False)


def _report_build(component: str):
    """Keep the commit this worker/beat runs in Redis, for manage's Diagnose page."""

    def handler(**_kwargs) -> None:
        from hubra.core.build_info import start_heartbeat

        from hubra.core.roles import build_component

        start_heartbeat(build_component(component), celery_app.flask_app)

    return handler


signals.worker_ready.connect(_report_build("worker"), weak=False)
signals.beat_init.connect(_report_build("beat"), weak=False)

# The background job dashboard (manage › Diagnostics › Background jobs).
from hubra.core.tasks import job_signals  # noqa: E402,F401
