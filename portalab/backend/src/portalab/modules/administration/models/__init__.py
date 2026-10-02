"""Schemas ``config`` and ``admin`` (specs/020-administration/data-model.md).

``config.settings`` holds one row per (key, scope, scope_ref): ``scope_ref`` is ``''`` for global values, the
module/plugin name, or the user id. User-scope rows are personal data of class ``preference`` (erased and
exported through Administration's privacy participants). Sensitive values are stored as an encrypted envelope.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id

SCOPES: tuple[str, ...] = ("global", "module", "plugin", "user")
POLICY_MODES: tuple[str, ...] = ("default", "lock", "bound")
TOGGLE_KINDS: tuple[str, ...] = ("module", "plugin", "connector", "service", "automation")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class ConfigBase(DeclarativeBase):
    metadata = schema_metadata("config")


class AdminBase(DeclarativeBase):
    metadata = schema_metadata("admin")


class Setting(ConfigBase):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint(_in("scope", SCOPES), name="scope"),
        UniqueConstraint("key", "scope", "scope_ref", name="uq_settings_key_scope"),
        Index("ix_settings_scope_ref", "scope", "scope_ref"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Policy(ConfigBase):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint(_in("mode", POLICY_MODES), name="mode"),
        Index("uq_policies_active_key", "key", unique=True, postgresql_where=text("removed_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    bounds: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    set_by: Mapped[UUID | None] = mapped_column()
    set_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class SettingHistory(ConfigBase):
    __tablename__ = "setting_history"
    __table_args__ = (
        Index("ix_setting_history_key_changed_at", "key", "changed_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    scope_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # user refs hashed: no PII
    old_value_redacted: Mapped[Any] = mapped_column(JSONB, nullable=True)
    new_value_redacted: Mapped[Any] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column()
    changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class ExtensionToggle(AdminBase):
    __tablename__ = "extension_toggles"
    __table_args__ = (
        CheckConstraint(_in("kind", TOGGLE_KINDS), name="kind"),
        UniqueConstraint("kind", "ref", name="uq_extension_toggles_kind_ref"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column()
    changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class FirstRun(AdminBase):
    __tablename__ = "first_run"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    completed_by: Mapped[UUID | None] = mapped_column()
