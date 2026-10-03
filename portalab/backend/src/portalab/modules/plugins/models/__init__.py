"""Schema ``plugins`` (specs/023 data-model): installed plugins and their state, append-only versions (with
the manifest, the on-disk package and its checksum), the contribution ledger, the install-time review
(consent) record, bounded error statistics, append-only purges and update runs. Users are referenced by id
(FK in the migration only). Plugin data itself lives in schemas ``plugin_<key>``."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

STATES = (
    "installed",
    "needs_configuration",
    "enabled",
    "disabled",
    "update_pending",
    "update_failed",
    "incompatible",
    "quarantined",
    "archived",
)


class PluginsBase(DeclarativeBase):
    metadata = schema_metadata("plugins")


class Plugin(PluginsBase):
    __tablename__ = "plugins"
    __table_args__ = (
        CheckConstraint("state IN (" + ", ".join(f"'{s}'" for s in STATES) + ")", name="state"),
        CheckConstraint("scope IN ('portal', 'user')", name="scope"),
        CheckConstraint("source IN ('admin_upload', 'local_dir', 'marketplace')", name="source"),
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("a plugin name"))
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    maturity: Mapped[str] = mapped_column(String(12), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    needs_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_by: Mapped[UUID | None] = mapped_column()
    installed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    quarantine_reason: Mapped[str | None] = mapped_column(
        String(300), info=not_personal("a technical reason")
    )
    last_error_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PluginVersion(PluginsBase):
    __tablename__ = "versions"
    __table_args__ = (
        CheckConstraint("status IN ('current', 'previous', 'staged', 'failed', 'probation')", name="status"),
        {"info": APPEND_ONLY_INFO},
    )

    plugin_key: Mapped[str] = mapped_column(ForeignKey("plugins.plugins.key"), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    package_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class VersionState(PluginsBase):
    """Mutable status of a version (``versions`` itself is append-only)."""

    __tablename__ = "version_states"

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    probation_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Contribution(PluginsBase):
    __tablename__ = "contributions"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'removed', 'conflict')", name="state"),
        Index("ix_contributions_plugin", "plugin_key", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    point: Mapped[str] = mapped_column(String(32), nullable=False)
    contribution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(8), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    detail: Mapped[str | None] = mapped_column(String(300), info=not_personal("a technical note"))
    registered_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Review(PluginsBase):
    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column()
    approved_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    extension_points: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    events: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    personal_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class ErrorStat(PluginsBase):
    __tablename__ = "error_stats"
    __table_args__ = (
        CheckConstraint("kind IN ('route', 'event', 'action', 'widget', 'job', 'load', 'hook')", name="kind"),
    )

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sample: Mapped[str | None] = mapped_column(String(300), info=not_personal("a sanitized error type"))


class Purge(PluginsBase):
    __tablename__ = "purges"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column()
    exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    export_ref: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    schema_dropped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UpdateRun(PluginsBase):
    __tablename__ = "update_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'migrated', 'pending_restart', 'probation', 'succeeded', 'rolled_back', "
            "'failed')",
            name="status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, info=not_personal("a sanitized error"))
    probation_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
