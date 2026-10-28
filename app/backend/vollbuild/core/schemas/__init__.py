"""Schemas package — re-exports all Marshmallow schemas."""

from vollbuild.core.schemas.role import RoleSchema, RoleCreateSchema
from vollbuild.core.schemas.member import (
    MembershipTierSchema,
    MembershipTierCreateSchema,
    MemberSchema,
    MemberCreateSchema,
    MemberUpdateSchema,
)
from vollbuild.core.schemas.application import (
    ApplicationSchema,
    ApplicationCreateSchema,
)
from vollbuild.core.schemas.group import (
    GroupSchema,
    GroupCreateSchema,
    GroupUpdateSchema,
)
from vollbuild.core.schemas.function import (
    FunctionSchema,
    FunctionCreateSchema,
    FunctionUpdateSchema,
    FunctionHolderSchema,
)
from vollbuild.core.schemas.managed_mail import ManagedMailAddressSchema
from vollbuild.core.schemas.event import (
    ClubEventSchema,
    ClubEventCreateSchema,
    ClubEventUpdateSchema,
)
from vollbuild.core.schemas.poll import (
    PollOptionSchema,
    PollSchema,
    PollCreateSchema,
    VoteSchema,
)
from vollbuild.core.schemas.finance import (
    TransactionCategorySchema,
    TransactionCategoryCreateSchema,
    TransactionSchema,
    TransactionCreateSchema,
    InvoiceSchema,
    InvoiceCreateSchema,
    InvoiceUpdateSchema,
)

from vollbuild.core.schemas.settings import SettingSchema, SettingWriteSchema
from vollbuild.core.schemas.code import (
    CodeSchema,
    CodeCreateSchema,
    CodeUpdateSchema,
)
from vollbuild.core.schemas.notification import NotificationSchema
from vollbuild.core.schemas.audit import AuditEntrySchema

__all__ = [
    # Role
    "RoleSchema",
    "RoleCreateSchema",
    # Membership tier
    "MembershipTierSchema",
    "MembershipTierCreateSchema",
    # Member
    "MemberSchema",
    "MemberCreateSchema",
    "MemberUpdateSchema",
    # Application
    "ApplicationSchema",
    "ApplicationCreateSchema",
    # Group
    "GroupSchema",
    "GroupCreateSchema",
    "GroupUpdateSchema",
    # Function
    "FunctionSchema",
    "FunctionCreateSchema",
    "FunctionUpdateSchema",
    "FunctionHolderSchema",
    # ManagedMailAddress
    "ManagedMailAddressSchema",
    # Event
    "ClubEventSchema",
    "ClubEventCreateSchema",
    "ClubEventUpdateSchema",
    # Poll
    "PollOptionSchema",
    "PollSchema",
    "PollCreateSchema",
    "VoteSchema",
    # Finance
    "TransactionCategorySchema",
    "TransactionCategoryCreateSchema",
    "TransactionSchema",
    "TransactionCreateSchema",
    "InvoiceSchema",
    "InvoiceCreateSchema",
    "InvoiceUpdateSchema",
    # Settings KV
    "SettingSchema",
    "SettingWriteSchema",
    # Notification
    "NotificationSchema",
    # Audit
    "AuditEntrySchema",
    # Code
    "CodeSchema",
    "CodeCreateSchema",
    "CodeUpdateSchema",
]
