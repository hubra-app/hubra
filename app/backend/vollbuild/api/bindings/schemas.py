"""Marshmallow schemas for InternalKey and Binding serialization."""

from __future__ import annotations

from marshmallow import fields, Schema


class InternalKeySchema(Schema):
    id = fields.Integer()
    key = fields.String()
    allow_multiple = fields.Boolean()
    is_protected = fields.Boolean()
    label = fields.String(allow_none=True)
    has_value = fields.Boolean()
    masked_value = fields.String(allow_none=True)
    sensitive = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class InternalKeyCreateSchema(Schema):
    key = fields.String(required=True)
    allow_multiple = fields.Boolean(load_default=False)
    is_protected = fields.Boolean(load_default=False)
    label = fields.String(allow_none=True, load_default=None)


class InternalKeyUpdateSchema(Schema):
    label = fields.String(allow_none=True)
    allow_multiple = fields.Boolean(allow_none=True)
    is_protected = fields.Boolean(allow_none=True)


class BindingSchema(Schema):
    id = fields.Integer()
    type = fields.String()
    source_id = fields.String()
    source_attribute = fields.String()
    key_id = fields.Integer()
    key_name = fields.String(allow_none=True)
    allow_multiple = fields.Boolean()
    validator = fields.String()
    is_protected = fields.Boolean()
    enabled = fields.Boolean()
    validation_status = fields.String()
    validation_error = fields.String(allow_none=True)
    source_label = fields.String(allow_none=True)
    resolved_value = fields.String(allow_none=True)
    resolved_sensitive = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class BindingCreateSchema(Schema):
    type = fields.String(required=True)
    source_id = fields.String(required=True)
    source_attribute = fields.String(required=True)
    key_id = fields.Integer(required=True)
    validator = fields.String(load_default="none")
    enabled = fields.Boolean(load_default=True)
    is_protected = fields.Boolean(load_default=False)


class BindingUpdateSchema(Schema):
    type = fields.String(allow_none=True)
    source_id = fields.String(allow_none=True)
    source_attribute = fields.String(allow_none=True)
    key_id = fields.Integer(allow_none=True)
    validator = fields.String(allow_none=True)
    enabled = fields.Boolean(allow_none=True)
    is_protected = fields.Boolean(allow_none=True)


class BindingToggleSchema(Schema):
    enabled = fields.Boolean(required=True)
