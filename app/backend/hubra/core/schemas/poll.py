"""Marshmallow schemas for Poll, PollOption, and voting."""

from flask import g
from marshmallow import EXCLUDE, RAISE, fields, validate
from sqlalchemy import select, func

from hubra.core.extensions import ma, db
from hubra.core.models.poll import Poll, PollOption, PollVote


class PollOptionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PollOption
        load_instance = True
        unknown = EXCLUDE
        exclude = ("poll", "poll_votes")

    vote_count = fields.Method("get_vote_count", dump_only=True)

    def get_vote_count(self, obj):
        return (
            db.session.scalar(select(func.count()).where(PollVote.option_id == obj.id))
            or 0
        )


class PollSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Poll
        load_instance = True
        unknown = EXCLUDE
        exclude = ("votes",)

    closes_at = fields.DateTime(allow_none=True)
    options = fields.List(fields.Nested(PollOptionSchema), dump_only=True)
    total_votes = fields.Method("get_total_votes", dump_only=True)
    created_by_id = fields.Integer(dump_only=True, allow_none=True)
    is_required = fields.Boolean(dump_only=True)
    allow_proxy = fields.Boolean(dump_only=True)
    max_proxies_per_member = fields.Int(dump_only=True)
    required_group_ids = fields.List(fields.Integer(), dump_only=True, allow_none=True)
    required_function_ids = fields.List(
        fields.Integer(), dump_only=True, allow_none=True
    )

    my_vote = fields.Method("get_my_vote", dump_only=True)

    def get_total_votes(self, obj):
        return (
            db.session.scalar(select(func.count()).where(PollVote.poll_id == obj.id))
            or 0
        )

    def get_my_vote(self, obj):
        """Index of the option the signed-in member chose, or None."""
        member_id = _current_member_id()
        if member_id is None:
            return None
        option_id = db.session.scalar(
            select(PollVote.option_id).where(
                PollVote.poll_id == obj.id, PollVote.member_id == member_id
            )
        )
        if option_id is None:
            return None
        ids = sorted(o.id for o in obj.options)
        return ids.index(option_id) if option_id in ids else None


def _current_member_id() -> int | None:
    """The signed-in member's id, looked up once per request."""
    if "poll_member_id" not in g:
        from hubra.api.auth.helpers import get_current_member

        try:
            g.poll_member_id = get_current_member().id
        except Exception:
            g.poll_member_id = None
    return g.poll_member_id


# ── Write schemas ─────────────────────────────────────────────────────────────


class _PollOptionInputSchema(ma.Schema):
    label = fields.Str(required=True, validate=validate.Length(min=1, max=255))


class PollCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    question = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    closes_at = fields.DateTime(allow_none=True, load_default=None)
    options = fields.List(
        fields.Nested(_PollOptionInputSchema),
        required=True,
        validate=validate.Length(min=2),
    )
    is_required = fields.Boolean(load_default=False)
    required_group_ids = fields.List(
        fields.Integer(), load_default=None, allow_none=True
    )
    required_function_ids = fields.List(
        fields.Integer(), load_default=None, allow_none=True
    )
    allow_proxy = fields.Boolean(load_default=False)
    max_proxies_per_member = fields.Int(
        load_default=1, validate=validate.Range(min=1, max=20)
    )


class PollUpdateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    question = fields.Str(validate=validate.Length(min=1, max=255))
    closes_at = fields.DateTime(allow_none=True, load_default=None)
    options = fields.List(
        fields.Nested(_PollOptionInputSchema),
        validate=validate.Length(min=2),
    )
    is_required = fields.Boolean()
    required_group_ids = fields.List(fields.Integer(), allow_none=True)
    required_function_ids = fields.List(fields.Integer(), allow_none=True)
    allow_proxy = fields.Boolean()
    max_proxies_per_member = fields.Int(validate=validate.Range(min=1, max=20))


class VoteSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    option_index = fields.Int(required=True, validate=validate.Range(min=0))
    on_behalf_of = fields.Int(load_default=None, allow_none=True)
