"""Marshmallow schema for ManagedMailAddress.

Used for binding-attribute discovery (introspecting which MMA fields are
bindable). Not the general API serialization schema — that lives in the
mail service's ``serialize`` function.
"""

from marshmallow import EXCLUDE, fields

from vollbuild.extensions import ma
from vollbuild.core.models.managed_mail import ManagedMailAddress


class ManagedMailAddressSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ManagedMailAddress
        load_instance = True
        unknown = EXCLUDE
        exclude = (
            "id",
            "is_system",
            "address_type",
            "is_protected",
            "forwarding_enabled",
            "cached_forward_targets",
            "fixed_forward_targets",
            "provisioning_status",
            "wildduck_user_id",
            "wildduck_filter_id",
            "kind",
            "owner_type",
            "owner_id",
            "forward_enabled",
            "quota_bytes",
            "retention",
            "from_whitelist",
            "last_quota_alert_at",
            "wildduck_id",
            "wildduck_type",
            "last_synced_at",
            "sync_state",
            "sync_error",
            "mailbox_password_encrypted",
            "created_at",
            "updated_at",
            "mail_prefix",
            "display_name",
        )

    enabled = fields.Boolean(allow_none=True)
