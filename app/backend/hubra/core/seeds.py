from __future__ import annotations


import click
import json
from sqlalchemy import select


def run_seeds(db):
    from hubra.core.models.setting import Setting
    from hubra.core.models.translation import Translation
    from hubra.core.models.managed_mail import ManagedMailAddress

    session = db.session

    from flask import current_app as _ca

    # ── 1. Settings KV ─────────────────────────────────────────────────────────

    from hubra.api.settings.services import SettingService

    _kv_defaults = [
        (
            "club.name",
            "Hubra",
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
            _ca.config.get("MAIL_DOMAIN") or "hubra.club",
            "general",
            False,
            True,
            False,
            "domain",
            "Mail domain",
            "Domain used for member email addresses and mail routing (e.g. hubra.club)",
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
            "noreply@hubra.club",
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
        / "seed_data"
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

    # ── 1c. Module catalog (public schema) ──────────────────────────────────

    from hubra.core.modules import sync_catalog

    sync_catalog()

    # ── 2. TransactionCategories ───────────────────────────────────────────────

    from hubra.api.finance.services import TransactionCategoriesService

    tx_cat_defs = [
        {"name": "Membership", "color": "#2596be"},
        {"name": "Events", "color": "#27ae60"},
        {"name": "Consumables", "color": "#f39c12"},
        {"name": "Utilities", "color": "#e74c3c"},
        {"name": "Donation", "color": "#9b59b6"},
        {"name": "Other", "color": "#95a5a6"},
    ]
    for tcd in tx_cat_defs:
        from hubra.core.models.finance import TransactionCategory

        existing = session.scalar(
            select(TransactionCategory).where(TransactionCategory.name == tcd["name"])
        )
        if existing is None:
            TransactionCategoriesService.create(tcd)

    # ── 3. Vorstand group ──────────────────────────────────────────────────────

    from hubra.core.models.group import Group

    vorstand = session.scalar(select(Group).where(Group.name == "Vorstand"))
    if vorstand is None:
        from hubra.api.groups.services import GroupsService

        vorstand = GroupsService.create(
            {"name": "Vorstand", "description": "Vorstand / Board of directors"},
            actor_id=None,
        )
        vorstand.is_default = True
        session.flush()

    # ── 4. Functions ───────────────────────────────────────────────────────────

    from hubra.api.functions.services import FunctionService
    from hubra.core.models.function import Function

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

    from hubra.core.services import managed_mail as mma_service

    for group in session.scalars(select(Group)).all():
        existing = session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == group.id,
            )
        )
        if existing is None:
            mma_service.auto_create_mma_for_group(group.id)

    from hubra.core.models.function import Function

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
    club_domain = _cd.value if _cd and _cd.value else "hubra.club"

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

        from hubra.core.services.mail_provisioning import (
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

    from hubra.api.i18n import services as i18n_services

    _seeds_dir = _pathlib.Path(__file__).resolve().parent / "seed_data" / "translations"
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

    refresh_shipped_translations(session, _seeds_dir)
    session.flush()

    session.commit()


def refresh_shipped_translations(session, seeds_dir) -> None:
    """Bring stored translations up to date with the shipped ones.

    A stored value that still equals a value an earlier release shipped (listed
    in superseded.json) was never edited by the club, so it is replaced with the
    current value; retired keys are removed. Edited values are left alone.
    Runs on the public schema and on every club schema.
    """
    import pathlib as _pathlib

    from hubra.core.models.tenant import Tenant
    from hubra.core.models.translation import Translation
    from hubra.core.tenant.context import reset_search_path, set_search_path

    path = _pathlib.Path(seeds_dir) / "superseded.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        superseded = json.load(f)
    current: dict[str, dict[str, str]] = {}
    for locale in superseded.get("values", {}):
        current_path = _pathlib.Path(seeds_dir) / f"{locale}.json"
        if current_path.exists():
            with open(current_path, encoding="utf-8") as f:
                current[locale] = json.load(f)
    retired = set(superseded.get("retired", []))

    def refresh_schema() -> int:
        changed = 0
        for row in session.scalars(select(Translation)).all():
            if row.alias_for:
                continue
            old_values = superseded.get("values", {}).get(row.locale, {}).get(row.key)
            if row.key in retired and (not row.value or old_values is None or row.value in old_values):
                session.delete(row)
                changed += 1
                continue
            new_value = current.get(row.locale, {}).get(row.key)
            if new_value and old_values and row.value in old_values and row.value != new_value:
                row.value = new_value
                row.needs_attention = False
                row.is_missing = False
                changed += 1
            elif new_value and (row.value or "").strip() == row.key:
                # A text that is just its key shows the key in the app.
                row.value = new_value
                row.needs_attention = False
                row.is_missing = False
                changed += 1
            elif new_value and not row.value and row.is_missing:
                row.value = new_value
                row.needs_attention = False
                row.is_missing = False
                changed += 1
        return changed

    total = refresh_schema()
    session.flush()
    for tenant in session.scalars(select(Tenant)).all():
        set_search_path(tenant.id)
        total += refresh_schema()
        session.flush()
    reset_search_path()
    if total:
        click.echo(f"  Updated {total} translations to the current wording.")
