"""Marshmallow schemas for Application."""

from marshmallow import EXCLUDE, RAISE, fields

from hubra.core.extensions import ma
from hubra.core.models.application import Application


class ApplicationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Application
        load_instance = True
        unknown = EXCLUDE
        exclude = ("wants_tier",)

    applied_at = fields.DateTime(dump_only=True)
    wants_tier_name = fields.Method("get_wants_tier_name", dump_only=True)

    def get_wants_tier_name(self, obj):
        return obj.wants_tier.name if obj.wants_tier else None


class ApplicationCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True)
    email = fields.Email(required=True)
    wants_tier_id = fields.Int(allow_none=True, load_default=None)
