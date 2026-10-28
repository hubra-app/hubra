"""Application service — business logic for membership applications."""

from __future__ import annotations

import random

from flask import current_app

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.application import Application
from hubra.core.models.member import Member

_AVATAR_COLORS = [
    "#2596be",
    "#1f61d8",
    "#fe64ac",
    "#1c2740",
    "#8e97a7",
    "#ff4d3d",
    "#1f9d57",
    "#f39c12",
    "#9b59b6",
    "#fece2b",
]


class ApplicationService:
    """Operations on a single application."""

    @staticmethod
    def get(application_id: int) -> Application:
        """Return an application or raise 404."""
        application = db.session.scalar(
            select(Application)
            .where(Application.id == application_id)
            .options(selectinload(Application.wants_tier))
        )
        if application is None:
            raise_error(404, "NOT_FOUND", f"Application {application_id} not found")
        return application  # type: ignore[return-value]

    @staticmethod
    def approve(application_id: int, actor_id: int) -> Member:
        """Approve an application, create a member, and dispatch side-effects.

        Returns the created member (committed).
        """
        from hubra.api.members.services import MembersService

        application = ApplicationService.get(application_id)

        member, temp_password = MembersService.create_from_application(application)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="approve_application",
            target_type="Member",
            target_id=member.id,
            target_label=member.name,
        )

        db.session.delete(application)

        # WildDuck mailbox — async via Celery
        if member.public_email:
            try:
                from hubra.core.tasks.wildduck import create_wildduck_user

                create_wildduck_user.delay(member.id)
            except Exception:
                current_app.logger.exception(
                    "Could not queue WildDuck mailbox for member %s", member.id
                )

        # Welcome email with the temporary password — non-blocking. Skipped
        # for applicants who already had an account (signed-in join requests).
        if temp_password:
            from hubra.core.services import email as email_svc

            login_email = member.public_email or member.email
            email_svc.send_welcome(
                member.email,
                member.name,
                login_email,
                temp_password,
                lang=getattr(member, "language", "de-CH") or "de-CH",
            )

        db.session.refresh(member)
        return member  # type: ignore[return-value]

    @staticmethod
    def decline(application_id: int, actor_id: int) -> None:
        """Decline and delete an application."""
        application = ApplicationService.get(application_id)

        log_audit(
            actor_id=actor_id,
            action="decline_application",
            target_type="Application",
            target_id=application.id,
            target_label=application.name,
        )

        db.session.delete(application)

    @staticmethod
    def delete(application_id: int) -> None:
        """Delete an application without audit trail."""
        application = ApplicationService.get(application_id)
        db.session.delete(application)


class ApplicationsService:
    """Operations on the application collection."""

    @staticmethod
    def list() -> list[Application]:
        """Return all applications ordered by applied_at descending."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Application)
            .order_by(Application.applied_at.desc())
            .options(selectinload(Application.wants_tier))
        ).all()

    @staticmethod
    def submit(
        first_name: str, last_name: str, email: str, wants_tier_id: int | None = None
    ) -> Application:
        """Submit a new application. Raises 409 on conflicts."""
        from hubra.core.models.user import User as _User

        existing_user = db.session.scalar(select(_User).where(_User.email == email))
        if existing_user:
            # A former member (archived) may ask to come back.
            existing_member = db.session.scalar(
                select(Member.id).where(
                    Member.user_id == existing_user.id, Member.archived_at.is_(None)
                )
            )
            if existing_member:
                raise_error(
                    409, "CONFLICT", "An account with this email already exists"
                )

        if db.session.scalar(select(Application.id).where(Application.email == email)):
            raise_error(
                409, "CONFLICT", "An application from this email is already pending"
            )

        color = random.choice(_AVATAR_COLORS)

        app = Application(
            name=f"{first_name} {last_name}",
            email=email,
            wants_tier_id=int(wants_tier_id) if wants_tier_id else None,
            avatar_color=color,
        )
        db.session.add(app)
        return app  # type: ignore[return-value]
