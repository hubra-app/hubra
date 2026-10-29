"""Marshmallow schemas for the Setting KV store."""

from marshmallow import RAISE, fields

from hubra.core.extensions import ma


class SettingSchema(ma.Schema):
    """Read schema for a single Setting KV entry.

    Sensitive values are masked as ``"****"`` so they are never exposed
    in GET responses.  The write schema accepts the real value.
    """

    key = fields.Str()
    value = fields.Method("_get_value")
    namespace = fields.Str()
    sensitive = fields.Bool()
    required = fields.Bool()
    restricted = fields.Bool()
    validation_type = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    label = fields.Str(allow_none=True)
    is_default = fields.Bool()
    default_value = fields.Method("_get_default_value")

    def _get_value(self, obj):
        if getattr(obj, "sensitive", False):
            return "****" if obj.value else None
        return obj.value

    def _get_default_value(self, obj):
        if getattr(obj, "sensitive", False):
            return "****" if obj.default_value else None
        return obj.default_value


class SettingWriteSchema(ma.Schema):
    """PUT body: value required; all other fields optional."""

    class Meta:
        unknown = RAISE

    value = fields.Str(allow_none=True, required=True)
    namespace = fields.Str(load_default=None)
    sensitive = fields.Bool(load_default=None)
    required = fields.Bool(load_default=None)
    restricted = fields.Bool(load_default=None)
    validation_type = fields.Str(allow_none=True, load_default=None)
    description = fields.Str(allow_none=True, load_default=None)
    label = fields.Str(allow_none=True, load_default=None)
