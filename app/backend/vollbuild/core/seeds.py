from __future__ import annotations


import click
import json
from sqlalchemy import select


def _get_or_create(session, model, lookup_kwargs, create_kwargs=None):
    stmt = select(model)
    for attr, val in lookup_kwargs.items():
        stmt = stmt.where(getattr(model, attr) == val)
    obj = session.scalar(stmt)
    if obj is None:
        kwargs = {**lookup_kwargs, **(create_kwargs or {})}
        obj = model(**kwargs)
        session.add(obj)
        session.flush()
    return obj


def run_seeds(db):
    from vollbuild.core.models.setting import Setting
    from vollbuild.core.models.translation import Translation
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.models.feature_flag import FeatureFlag
    from vollbuild.core.models.feature import Feature

    session = db.session

    from flask import current_app as _ca

    # ── 1. Settings KV ─────────────────────────────────────────────────────────

    from vollbuild.api.settings.services import SettingService

    _kv_defaults = [
        (
            "club.name",
            "VollBuild Makerspace",
            "general",
            False,
            True,
            False,
            None,
            "Club name",
            "Name of the club, shown on invoices and member-facing pages",
        ),
        (
            "mail.domain",
            _ca.config.get("MAIL_DOMAIN") or "vollbuild.ch",
            "general",
            False,
            True,
            False,
            "domain",
            "Mail domain",
            "Domain used for member email addresses and mail routing (e.g. vollbuild.ch)",
        ),
        (
            "club.currency",
            "CHF",
            "general",
            False,
            True,
            False,
            None,
            "Currency",
            "Default currency for invoices and financial reports",
        ),
        (
            "club.email_schema",
            "firstname.lastname",
            "general",
            False,
            True,
            False,
            None,
            "Email schema",
            "Pattern for member email addresses (e.g. firstname.lastname)",
        ),
        (
            "club.notification_sender_email",
            "noreply@vollbuild.ch",
            "general",
            False,
            True,
            False,
            "email",
            "Notification sender email",
            "From address for all system notification emails",
        ),
        (
            "club.notification_sender_name",
            "VollBuild Notifications",
            "general",
            False,
            True,
            False,
            None,
            "Notification sender name",
            "Display name for system notification emails",
        ),
        (
            "Club.Banking.Iban",
            "CH3706633740415352677",
            "club",
            False,
            False,
            False,
            "qr_iban",
            "QR-IBAN",
            "Swiss IBAN for invoice payments (should be a QR-IBAN for QR-bill compatibility)",
        ),
        (
            "Club.Banking.Address",
            "",
            "club",
            False,
            False,
            False,
            None,
            "Club address",
            "Postal address shown on invoices (display-only — QR-bill uses structured fields below)",
        ),
        (
            "Club.Banking.Street",
            "",
            "club",
            False,
            False,
            False,
            None,
            "Street",
            "Creditor street name for QR-bill (e.g. Bahnhofstrasse)",
        ),
        (
            "Club.Banking.HouseNo",
            "",
            "club",
            False,
            False,
            False,
            None,
            "House number",
            "Creditor house number for QR-bill (e.g. 42)",
        ),
        (
            "Club.Banking.PostalCode",
            "",
            "club",
            False,
            False,
            False,
            None,
            "Postal code",
            "Creditor postal code for QR-bill (e.g. 8000)",
        ),
        (
            "Club.Banking.City",
            "",
            "club",
            False,
            False,
            False,
            None,
            "City",
            "Creditor city for QR-bill (e.g. Zurich)",
        ),
        (
            "Club.Banking.Country",
            "CH",
            "club",
            False,
            False,
            False,
            None,
            "Country",
            "Creditor country code for QR-bill (ISO 3166-1 alpha-2, e.g. CH)",
        ),
        (
            "Club.Contact.FinanceEmail",
            "",
            "club",
            False,
            False,
            False,
            "email",
            "Finance contact email",
            "Used for billing inquiries and as WildDuck send-as whitelist",
        ),
        (
            "Club.Finance.YearlyExpenses",
            "0",
            "club",
            False,
            False,
            False,
            "number",
            "Yearly expenses (CHF)",
            "Club's total yearly expenses — used for percentage/formula tier pricing",
        ),
        (
            "mail.smtp_host",
            _ca.config.get("SMTP_HOST") or _ca.config.get("ZONEMTA_SMTP_HOST") or "",
            "mail",
            False,
            True,
            False,
            "host",
            "SMTP host",
            "Outgoing SMTP server hostname",
        ),
        (
            "mail.smtp_port",
            str(
                _ca.config.get("SMTP_PORT")
                or _ca.config.get("ZONEMTA_SMTP_PORT")
                or 587
            ),
            "mail",
            False,
            True,
            False,
            "port",
            "SMTP port",
            "Outgoing SMTP server port (typically 587 for STARTTLS)",
        ),
        (
            "backup.s3_endpoint",
            _ca.config.get("BACKUP_S3_ENDPOINT") or "",
            "backup",
            False,
            False,
            False,
            "url",
            "S3 endpoint URL",
            "Contabo S3-compatible endpoint URL (e.g. https://eu2.contabostorage.com)",
        ),
        (
            "backup.s3_bucket",
            _ca.config.get("BACKUP_S3_BUCKET") or "",
            "backup",
            False,
            False,
            False,
            None,
            "S3 bucket name",
            "Name of the S3 bucket where encrypted backups are stored",
        ),
        (
            "backup.s3_access_key",
            _ca.config.get("BACKUP_S3_ACCESS_KEY") or "",
            "backup",
            True,
            False,
            False,
            None,
            "S3 access key",
            "Access key ID for S3 authentication (stored encrypted, masked in UI)",
        ),
        (
            "backup.s3_secret_key",
            _ca.config.get("BACKUP_S3_SECRET_KEY") or "",
            "backup",
            True,
            False,
            False,
            None,
            "S3 secret key",
            "Secret access key for S3 authentication (stored encrypted, masked in UI)",
        ),
        (
            "backup.s3_region",
            _ca.config.get("BACKUP_S3_REGION") or "default",
            "backup",
            False,
            False,
            False,
            None,
            "S3 region",
            "Region for the S3 endpoint (typically 'default' for Contabo)",
        ),
    ]

    for (
        _key,
        _val,
        _ns,
        _sensitive,
        _required,
        _restricted,
        _vtype,
        _label,
        _desc,
    ) in _kv_defaults:
        existing = session.get(Setting, _key)
        if existing is None:
            SettingService.upsert(
                _key,
                {
                    "value": _val,
                    "namespace": _ns,
                    "sensitive": _sensitive,
                    "required": _required,
                    "restricted": _restricted,
                    "validation_type": _vtype,
                    "label": _label,
                    "description": _desc,
                },
            )
        else:
            if existing.label is None:
                existing.label = _label
            if existing.description is None:
                existing.description = _desc
    session.flush()

    # ── 1b. Settings defaults from JSON ────────────────────────────────────────

    import pathlib as _pathlib

    _settings_seed_path = (
        _pathlib.Path(__file__).resolve().parent
        / "seeds"
        / "settings"
        / "settings.json"
    )
    if _settings_seed_path.exists():
        with open(_settings_seed_path, encoding="utf-8") as _f:
            _settings_defaults = json.load(_f)
        for _sd in _settings_defaults:
            _skey = _sd["key"]
            existing_s = session.get(Setting, _skey)
            if existing_s is None:
                SettingService.upsert(
                    _skey,
                    {
                        "value": _sd.get("value"),
                        "namespace": _sd.get("namespace", "general"),
                        "validation_type": _sd.get("validation_type"),
                        "label": _sd.get("label"),
                        "description": _sd.get("description"),
                    },
                )
                existing_s = session.get(Setting, _skey)
                if existing_s is not None:
                    existing_s.default_value = _sd.get("value")
                    existing_s.is_default = True
            else:
                if existing_s.default_value is None:
                    existing_s.default_value = _sd.get("value")
                if existing_s.label is None:
                    existing_s.label = _sd.get("label")
                if existing_s.description is None:
                    existing_s.description = _sd.get("description")
        session.flush()

    # ── 1c. Feature flags (legacy) ───────────────────────────────────────────

    _feature_flag_defaults = [
        ("mail", True, "Mail", "Club email provisioning"),
        ("backup", False, "Backup", "Automated encrypted database backups"),
        (
            "finance",
            True,
            "Finance",
            "Member invoices, transactions, and financial reports",
        ),
        ("events", True, "Events", "Club events, workshops, and gatherings"),
        ("polls", True, "Polls", "Member polls and voting"),
        ("posts", True, "Posts", "Club announcements and community posts"),
    ]
    for _ff_key, _ff_enabled, _ff_label, _ff_desc in _feature_flag_defaults:
        _existing_ff = session.get(FeatureFlag, _ff_key)
        if _existing_ff is None:
            session.add(
                FeatureFlag(
                    key=_ff_key,
                    enabled=_ff_enabled,
                    label=_ff_label,
                    description=_ff_desc,
                )
            )
        else:
            _existing_ff.enabled = _ff_enabled
            _existing_ff.label = _ff_label
            _existing_ff.description = _ff_desc
    session.flush()

    # ── 1d. Feature catalog (public schema) ──────────────────────────────────

    _feature_catalog = [
        ("members", "Member Management", True, "Core member directory and profiles"),
        ("groups", "Groups", True, "Group management and communication"),
        ("functions", "Functions/Offices", True, "Club offices and function holders"),
        ("events", "Events", True, "Event creation and registration"),
        ("polls", "Polls", True, "Voting and polls"),
        ("posts", "Posts & News", True, "Internal news and posts"),
        ("finance", "Finances", True, "Transactions, invoices, billing"),
        ("mail", "Mail", True, "Club email provisioning"),
        ("inventory", "Inventory", False, "Equipment and inventory tracking"),
        ("bindings", "Bindings", False, "External API binding engine"),
        ("codes", "Encrypted Codes", False, "Secure code storage"),
        ("backups", "Backups", False, "Database backup management"),
    ]
    for _code, _name, _default, _desc in _feature_catalog:
        _existing = session.get(Feature, _code)
        if _existing is None:
            session.add(
                Feature(
                    code=_code,
                    name=_name,
                    default_enabled=_default,
                    description=_desc,
                )
            )
        else:
            _existing.name = _name
            _existing.default_enabled = _default
            _existing.description = _desc
    session.flush()

    # ── 2. TransactionCategories ───────────────────────────────────────────────

    from vollbuild.api.finance.services import TransactionCategoriesService

    tx_cat_defs = [
        {"name": "Membership", "color": "#2596be"},
        {"name": "Events", "color": "#27ae60"},
        {"name": "Consumables", "color": "#f39c12"},
        {"name": "Utilities", "color": "#e74c3c"},
        {"name": "Donation", "color": "#9b59b6"},
        {"name": "Other", "color": "#95a5a6"},
    ]
    for tcd in tx_cat_defs:
        from vollbuild.core.models.finance import TransactionCategory

        existing = session.scalar(
            select(TransactionCategory).where(TransactionCategory.name == tcd["name"])
        )
        if existing is None:
            TransactionCategoriesService.create(tcd)

    # ── 3. Vorstand group ──────────────────────────────────────────────────────

    from vollbuild.core.models.group import Group

    vorstand = session.scalar(select(Group).where(Group.name == "Vorstand"))
    if vorstand is None:
        from vollbuild.api.groups.services import GroupsService

        vorstand = GroupsService.create(
            {"name": "Vorstand", "description": "Vorstand / Board of directors"},
            actor_id=None,
        )
        vorstand.is_default = True
        session.flush()

    # ── 4. Functions ───────────────────────────────────────────────────────────

    from vollbuild.api.functions.services import FunctionService
    from vollbuild.core.models.function import Function

    function_defs = [
        {"name": "Kassier", "description": "Treasurer", "mail_prefix": "kassier"},
        {"name": "Präsidium", "description": "President", "mail_prefix": "praesidium"},
        {"name": "Aktuar", "description": "Secretary", "mail_prefix": "aktuar"},
    ]
    for fd in function_defs:
        existing_fn = session.scalar(
            select(Function).where(Function.name == fd["name"])
        )
        if existing_fn is None:
            FunctionService.create(
                name=fd["name"],
                description=fd["description"],
                max_holders=1,
            )
            session.flush()

    # ── 5b. Ensure MMAs exist for all groups and functions ───────────────────
    # GroupsService.create / FunctionService.create call auto_create_mma_for_*
    # internally, but that can fail silently (e.g. unique constraint, session
    # issues).  This step explicitly creates any missing MMAs so the mail tabs
    # always show seeded groups and functions.

    from vollbuild.services import managed_mail as mma_service

    for group in session.scalars(select(Group)).all():
        existing = session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == group.id,
            )
        )
        if existing is None:
            mma_service.auto_create_mma_for_group(group.id)

    from vollbuild.core.models.function import Function

    for fn in session.scalars(select(Function)).all():
        existing = session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "function",
                ManagedMailAddress.owner_id == fn.id,
            )
        )
        if existing is None:
            mma_service.auto_create_mma_for_function(fn.id)

    # ── 5. System ManagedMailAddress rows ──────────────────────────────────────

    _cd = session.get(Setting, "mail.domain")
    club_domain = _cd.value if _cd and _cd.value else "vollbuild.ch"

    system_defs = [
        ("noreply", "mailbox", True, "No-Reply", None),
        ("postmaster", "mailbox", True, "Postmaster", None),
    ]

    for prefix, addr_type, protected, display_name, fixed_targets in system_defs:
        address = f"{prefix}@{club_domain}"
        existing = session.scalar(
            select(ManagedMailAddress).where(ManagedMailAddress.address == address)
        )
        if existing is None:
            mma_service.create_system_address(
                address=address,
                address_type=addr_type,
                display_name=display_name,
                forward_targets=fixed_targets,
                is_protected=protected,
                domain=club_domain,
            )
        else:
            existing.is_system = True
            existing.display_name = display_name
            existing.is_protected = protected
            if fixed_targets:
                existing.fixed_forward_targets = json.dumps(fixed_targets)
    session.flush()

    system_alis_mmas = [
        ("info", "alias", True, "Info", [f"postmaster@{club_domain}"]),
        ("abuse", "alias", True, "Abuse", [f"postmaster@{club_domain}"]),
        ("*", "alias", True, "Catch-All", [f"postmaster@{club_domain}"]),
    ]

    session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == f"postmaster@{club_domain}"
        )
    )

    for prefix, addr_type, protected, display_name, fixed_targets in system_alis_mmas:
        address = f"{prefix}@{club_domain}"
        existing = session.scalar(
            select(ManagedMailAddress).where(ManagedMailAddress.address == address)
        )
        if existing is None:
            mma_service.create_system_address(
                address=address,
                address_type=addr_type,
                display_name=display_name,
                forward_targets=fixed_targets,
                is_protected=protected,
                domain=club_domain,
            )
        else:
            existing.is_system = True
            existing.display_name = display_name
            existing.is_protected = protected
            if fixed_targets:
                existing.fixed_forward_targets = json.dumps(fixed_targets)

    # ── 6b. Noreply system mailbox password ─────────────────────────────────

    noreply_mma = session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == f"noreply@{club_domain}"
        )
    )
    if noreply_mma is not None and not noreply_mma.mailbox_password_encrypted:
        import secrets as _secrets

        from vollbuild.core.services.mail_provisioning import (
            set_system_mailbox_password,
        )

        set_system_mailbox_password(noreply_mma, _secrets.token_urlsafe(24))
        session.flush()

    # ── 6c. Enable Vorstand group MMA ──────────────────────────────────────────

    vorstand_mma = session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == vorstand.id,
        )
    )
    if vorstand_mma is not None:
        vorstand_mma.enabled = True
        vorstand_mma.is_enabled = True
        vorstand_mma.is_protected = True
    session.flush()

    # ── 6d. Enable function MMAs ───────────────────────────────────────────────

    for fd in function_defs:
        fn = session.scalar(select(Function).where(Function.name == fd["name"]))
        if fn is not None:
            fn_mma = session.scalar(
                select(ManagedMailAddress).where(
                    ManagedMailAddress.owner_type == "function",
                    ManagedMailAddress.owner_id == fn.id,
                )
            )
            if fn_mma is not None:
                fn_mma.enabled = True
                fn_mma.is_enabled = True
                fn_mma.is_protected = True
    session.flush()

    # ── 6. Translations ────────────────────────────────────────────────────────

    from vollbuild.api.i18n import services as i18n_services

    _seeds_dir = _pathlib.Path(__file__).resolve().parent / "seeds" / "translations"
    for locale in ("en-GB", "de-CH"):
        path = _seeds_dir / f"{locale}.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        inserted = 0
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            existing = session.scalar(
                select(Translation).where(
                    Translation.locale == locale,
                    Translation.key == key,
                )
            )
            if existing is None:
                i18n_services.upsert_translation(locale, key, value)
                inserted += 1
        if inserted:
            click.echo(f"  Seeded {inserted} new translations for locale '{locale}'.")
    session.flush()

    session.commit()
