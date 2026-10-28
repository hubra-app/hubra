"""Marshmallow schemas for Role."""

from marshmallow import EXCLUDE, RAISE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.role import Role


class RoleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = True
        unknown = EXCLUDE
        exclude = ("members",)


class RoleCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(load_default=None, allow_none=True)
