"""Marshmallow schemas for Poll, PollOption, and voting."""

from marshmallow import EXCLUDE, RAISE, fields, validate
from sqlalchemy import select, func

from vollbuild.core.extensions import ma, db
from vollbuild.core.models.poll import Poll, PollOption, PollVote


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
    required_group_ids = fields.List(fields.Integer(), dump_only=True, allow_none=True)
    required_function_ids = fields.List(
        fields.Integer(), dump_only=True, allow_none=True
    )

    def get_total_votes(self, obj):
        return (
            db.session.scalar(select(func.count()).where(PollVote.poll_id == obj.id))
            or 0
        )


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


class VoteSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    option_index = fields.Int(required=True, validate=validate.Range(min=0))
