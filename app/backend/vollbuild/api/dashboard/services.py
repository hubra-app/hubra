"""Dashboard service — summary stats and growth data."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import func, select

from sqlalchemy.orm import selectinload

from vollbuild.extensions import db
from vollbuild.core.models.event import ClubEvent
from vollbuild.core.models.finance import Invoice, Transaction
from vollbuild.core.models.member import Member
from vollbuild.core.models.post import Post


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


class DashboardService:
    """Aggregated dashboard data."""

    @staticmethod
    def get_summary() -> dict:
        """Return dashboard summary stats, growth, and upcoming events."""
        today = date.today()

        active_members: int = (
            db.session.scalar(
                select(func.count(Member.id))
                .where(Member.status == "active")
                .where(Member.archived_at.is_(None))
            )
            or 0
        )

        thirty_days_ago = today - timedelta(days=30)
        member_delta: int = (
            db.session.scalar(
                select(func.count(Member.id))
                .where(Member.joined >= thirty_days_ago)
                .where(Member.archived_at.is_(None))
            )
            or 0
        )

        month_start = date(today.year, today.month, 1)
        month_end = _last_day_of_month(today.year, today.month)
        net_month = (
            db.session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.date >= month_start)
                .where(Transaction.date <= month_end)
            )
            or 0
        )

        open_invoices_row = db.session.execute(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.amount), 0),
            ).where(Invoice.status != "Paid")
        ).one()
        open_invoices: int = open_invoices_row[0] or 0
        open_invoices_amount = open_invoices_row[1] or 0

        upcoming_count: int = (
            db.session.scalar(
                select(func.count(ClubEvent.id)).where(ClubEvent.date >= today)
            )
            or 0
        )

        growth: list[int] = []
        for offset in range(11, -1, -1):
            month_num = today.month - offset
            year_num = today.year
            while month_num <= 0:
                month_num += 12
                year_num -= 1
            last_day = _last_day_of_month(year_num, month_num)
            count = (
                db.session.scalar(
                    select(func.count(Member.id))
                    .where(Member.joined <= last_day)
                    .where(Member.archived_at.is_(None))
                )
                or 0
            )
            growth.append(count)

        return {
            "stats": {
                "activeMembers": active_members,
                "memberDelta": member_delta,
                "netMonth": float(net_month),
                "openInvoices": open_invoices,
                "openInvoicesAmount": float(open_invoices_amount),
                "upcomingEvents": upcoming_count,
            },
            "growth": growth,
        }

    @staticmethod
    def get_upcoming_events(limit: int = 4) -> list[ClubEvent]:
        """Return upcoming events ordered by date ASC."""
        today = date.today()
        return db.session.scalars(  # type: ignore[return-value]
            select(ClubEvent)
            .where(ClubEvent.date >= today)
            .order_by(ClubEvent.date.asc())
            .limit(limit)
        ).all()

    @staticmethod
    def get_recent_posts(limit: int = 5) -> list[Post]:
        """Return the most recent posts ordered by created_at DESC."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.likes))
            .order_by(Post.created_at.desc())
            .limit(limit)
        ).all()
