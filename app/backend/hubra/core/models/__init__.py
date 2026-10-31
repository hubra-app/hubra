"""
Models package — import all models so Flask-Migrate can discover them.

Import order is significant:
  1. Global models (Tenant, Domain, User) have no inter-model FKs
     to domain models and live in the public schema.
  2. Role and MembershipTier have no inter-model FKs.
  3. Member (and its association table member_groups)
       must be imported before Group, which imports that table.
  4. All remaining models only hold FK references (resolved as strings by SA).
"""

from hubra.core.models.tenant import Tenant, GlobalAuditEntry
from hubra.core.models.domain import Domain
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant
from hubra.core.models.tenant_request import TenantRequest
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.role import MemberRoleScope, Permission, Role, RolePermission
from hubra.core.models.global_role import (
    GlobalRole,
    GlobalPermission,
    GlobalRolePermission,
    UserGlobalRole,
)
from hubra.core.models.member import (
    Member,
    MembershipTier,
    member_groups,
    member_roles,
)
from hubra.core.models.application import Application
from hubra.core.models.group import Group, GroupMembership
from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.models.event import ClubEvent, event_attendees, EventRegistration
from hubra.core.models.poll import Poll, PollOption, PollVote, PollProxy
from hubra.core.models.post import Post, PostLike, PostComment
from hubra.core.models.finance import Transaction, Invoice, TransactionCategory
from hubra.core.models.external_party import ExternalParty
from hubra.core.models.mail import MailboxFolder
from hubra.core.models.setting import Setting
from hubra.core.models.feature import Feature, TenantFeature
from hubra.core.models.translation import Translation
from hubra.core.models.translation_request import TranslationRequest
from hubra.core.models.notification import Notification
from hubra.core.models.audit import AuditEntry
from hubra.core.models.token import TokenBlocklist
from hubra.core.models.device_session import Device, Session
from hubra.core.models.account_session import AccountSession
from hubra.core.models.connected_app import (
    ConnectedApp,
    ConnectedAppEvent,
    ExternalAccount,
)
from hubra.core.models.inventory import InventoryItem, item_instructions
from hubra.core.models.password_reset import PasswordResetToken
from hubra.core.models.email_verification import EmailVerificationToken
from hubra.core.models.invoice_reminder import InvoiceReminderHistory
from hubra.core.models.code import Code
from hubra.core.models.internal_key import InternalKey
from hubra.core.models.binding import Binding
from hubra.core.models.backup import BackupRecord
from hubra.core.models.qrr_reference import QrrReference
from hubra.core.models.payment_plan import PaymentPlan
from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.plugin import (
    InstalledPlugin,
    PluginArchive,
    PluginRepository,
    PluginState,
    TrustedKey,
)

# Plugins import their own models when they load (hubra.core.plugins).

__all__ = [
    "AccountSession",
    "ConnectedApp",
    "ConnectedAppEvent",
    "ExternalAccount",
    "InstalledPlugin",
    "PluginArchive",
    "PluginRepository",
    "PluginState",
    "TrustedKey",
    "Tenant",
    "GlobalAuditEntry",
    "Domain",
    "User",
    "UserTenant",
    "TenantRequest",
    "PlatformSetting",
    "Role",
    "Permission",
    "RolePermission",
    "MemberRoleScope",
    "GlobalRole",
    "GlobalPermission",
    "GlobalRolePermission",
    "UserGlobalRole",
    "Member",
    "MembershipTier",
    "member_groups",
    "member_roles",
    "Application",
    "Group",
    "GroupMembership",
    "Function",
    "FunctionHolder",
    "ManagedMailAddress",
    "ClubEvent",
    "event_attendees",
    "EventRegistration",
    "Poll",
    "PollOption",
    "PollVote",
    "PollProxy",
    "Post",
    "PostLike",
    "PostComment",
    "Transaction",
    "Invoice",
    "TransactionCategory",
    "ExternalParty",
    "MailboxFolder",
    "Setting",
    "Feature",
    "TenantFeature",
    "Translation",
    "TranslationRequest",
    "Notification",
    "AuditEntry",
    "TokenBlocklist",
    "Device",
    "Session",
    "InventoryItem",
    "item_instructions",
    "PasswordResetToken",
    "EmailVerificationToken",
    "InvoiceReminderHistory",
    "Code",
    "InternalKey",
    "Binding",
    "BackupRecord",
    "QrrReference",
    "PaymentPlan",
    "ClubInvite",
]
