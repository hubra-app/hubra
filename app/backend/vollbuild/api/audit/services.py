"""Audit service — paginated read-only audit log."""

from __future__ import annotations

from math import ceil

from sqlalchemy import func, select

from vollbuild.core.errors import raise_error
from vollbuild.core.extensions import db
from vollbuild.core.models.audit import AuditEntry


class AuditService:
    """Operations on a single audit entry."""

    @staticmethod
    def get(entry_id: int) -> AuditEntry:
        """Return an audit entry or raise 404."""
        entry = db.session.get(AuditEntry, entry_id)
        if entry is None:
            raise_error(404, "NOT_FOUND", "Audit entry not found")
        return entry  # type: ignore[return-value]


class AuditsService:
    """Operations on the audit collection."""

    @staticmethod
    def list(args, schema) -> dict:
        """List audit entries with filtering and pagination."""
        try:
            page = max(1, int(args.get("page", 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = min(200, max(1, int(args.get("pageSize", 25))))
        except (TypeError, ValueError):
            page_size = 25

        query = select(AuditEntry).order_by(AuditEntry.time.desc())

        actor_id_raw = args.get("actorId")
        if actor_id_raw:
            try:
                actor_id = int(actor_id_raw)
            except (TypeError, ValueError):
                raise_error(400, "VALIDATION_ERROR", "actorId must be an integer")
            query = query.where(AuditEntry.actor_id == actor_id)

        from_raw = args.get("from")
        if from_raw:
            try:
                from datetime import datetime, timezone

                from_dt = datetime.fromisoformat(from_raw)
                if from_dt.tzinfo is None:
                    from_dt = from_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                raise_error(400, "VALIDATION_ERROR", "'from' must be an ISO datetime")
            query = query.where(AuditEntry.time >= from_dt)

        to_raw = args.get("to")
        if to_raw:
            try:
                from datetime import datetime, timezone

                to_dt = datetime.fromisoformat(to_raw)
                if to_dt.tzinfo is None:
                    to_dt = to_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                raise_error(400, "VALIDATION_ERROR", "'to' must be an ISO datetime")
            query = query.where(AuditEntry.time <= to_dt)

        action_raw = args.get("action")
        if action_raw:
            query = query.where(AuditEntry.action == action_raw)

        total = db.session.scalar(select(func.count()).select_from(query.subquery()))
        items = db.session.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()

        return {
            "data": schema.dump(items),
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": ceil(total / page_size) if total else 0,
        }
