"""Marshmallow schemas for FeatureFlag, Feature, and TenantFeature."""

from marshmallow import RAISE, fields

from vollbuild.core.extensions import ma


class FeatureFlagSchema(ma.Schema):
    key = fields.Str()
    enabled = fields.Bool()
    label = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)


class FeatureFlagWriteSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    enabled = fields.Bool(required=True)


class FeatureSchema(ma.Schema):
    code = fields.Str()
    name = fields.Str()
    description = fields.Str(allow_none=True)
    default_enabled = fields.Bool()


class TenantFeatureSchema(ma.Schema):
    id = fields.Int()
    tenant_id = fields.Int()
    feature_code = fields.Str()
    enabled = fields.Bool()
    config = fields.Dict(allow_none=True)


class TenantFeatureWriteSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    enabled = fields.Bool(required=True)
    config = fields.Dict(allow_none=True)
