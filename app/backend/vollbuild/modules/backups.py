"""Backups: encrypted database backups."""

from vollbuild.core.modules import Blueprint, Module

module = Module(
    code="backups",
    name="Backups",
    description="Encrypted database backups",
    default_enabled=False,
    depends_on=("core",),
    blueprints=(
        Blueprint(
            "vollbuild.api.backups.routes",
            "backups_bp",
            "/api/v1/backups",
            v2=(("/api/v2/tenants/backups", "backups_bp_v2"),),
        ),
    ),
    # Shown as a tab of the System screen.
    tables=("backup_record",),
)
