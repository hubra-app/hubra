"""Marshmallow schemas for Notification."""

from marshmallow import EXCLUDE, fields

from vollbuild.extensions import ma
from vollbuild.core.models.notification import Notification


class NotificationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Notification
        load_instance = True
        unknown = EXCLUDE
        exclude = ("member",)

    time = fields.DateTime(dump_only=True)
