"""Marshmallow schemas for Group."""

from marshmallow import EXCLUDE, RAISE, fields, validate
from sqlalchemy import select, func

from hubra.core.extensions import ma, db
from hubra.core.models.group import Group
from hubra.core.models.member import member_groups
from hubra.core.schemas.counts import cached_count, clear_counts, prime_counts

_MEMBER_COUNT = "_member_count"


class GroupSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Group
        load_instance = True
        unknown = EXCLUDE
        exclude = ("members", "lead", "memberships", "child_groups")

    member_count = fields.Method("get_member_count", dump_only=True)
    lead_name = fields.Method("get_lead_name", dump_only=True)
    parent_group_name = fields.Method("get_parent_group_name", dump_only=True)

    # M5 new fields
    type = fields.Str(dump_default="interest_group")
    email_alias = fields.Str(allow_none=True, dump_default=None)
    is_public = fields.Bool(dump_default=True)
    self_join = fields.Bool(dump_default=False)
    parent_group_id = fields.Int(allow_none=True, dump_default=None)
    deleted_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)

    def dump(self, obj, *, many=None):
        if not (self.many if many is None else many):
            return super().dump(obj, many=many)
        groups = list(obj)
        prime_counts(groups, _MEMBER_COUNT, member_groups.c.group_id)
        try:
            return super().dump(groups, many=many)
        finally:
            clear_counts(groups, _MEMBER_COUNT)

    def get_member_count(self, obj):
        return cached_count(
            obj,
            _MEMBER_COUNT,
            lambda: db.session.scalar(
                select(func.count())
                .select_from(member_groups)
                .where(member_groups.c.group_id == obj.id)
            ),
        )

    def get_lead_name(self, obj):
        return obj.lead.name if obj.lead else None

    def get_parent_group_name(self, obj):
        return obj.parent_group.name if obj.parent_group else None


class GroupCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    lead_id = fields.Int(allow_none=True, load_default=None)
    description = fields.Str(allow_none=True, load_default=None)
    color = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"),
    )
    icon_name = fields.Str(allow_none=True, load_default=None)
    sessions = fields.Str(allow_none=True, load_default=None)
    tools = fields.Int(load_default=0)
    type = fields.Str(
        load_default="interest_group",
        validate=validate.OneOf(
            ["board", "committee", "team", "interest_group", "mailing_list"]
        ),
    )
    email_alias = fields.Str(allow_none=True, load_default=None)
    is_public = fields.Bool(load_default=True)
    self_join = fields.Bool(load_default=False)
    parent_group_id = fields.Int(allow_none=True, load_default=None)


class GroupUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    name = fields.Str(validate=validate.Length(min=1, max=255))
    lead_id = fields.Int(allow_none=True)
    description = fields.Str(allow_none=True)
    color = fields.Str(allow_none=True, validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))
    icon_name = fields.Str(allow_none=True)
    sessions = fields.Str(allow_none=True)
    tools = fields.Int()
    type = fields.Str(
        validate=validate.OneOf(
            ["board", "committee", "team", "interest_group", "mailing_list"]
        )
    )
    email_alias = fields.Str(allow_none=True)
    is_public = fields.Bool()
    self_join = fields.Bool()
    parent_group_id = fields.Int(allow_none=True)


class GroupMembershipSchema(ma.Schema):
    """Schema for group membership with role information."""

    class Meta:
        unknown = EXCLUDE

    id = fields.Int(dump_only=True)
    group_id = fields.Int(dump_only=True)
    member_id = fields.Int(dump_only=True)
    role = fields.Str(dump_default="member")
    joined_at = fields.DateTime(dump_only=True)
    notes = fields.Str(allow_none=True, dump_default=None)
    member_name = fields.Method("get_member_name", dump_only=True)
    member_email = fields.Method("get_member_email", dump_only=True)

    def get_member_name(self, obj):
        return obj.member.name if obj.member else None

    def get_member_email(self, obj):
        return obj.member.email if obj.member else None


class GroupMembershipUpdateSchema(ma.Schema):
    """Schema for updating a member's role in a group."""

    class Meta:
        unknown = RAISE

    role = fields.Str(
        required=True,
        validate=validate.OneOf(["leader", "member", "treasurer", "secretary"]),
    )
    notes = fields.Str(allow_none=True)
