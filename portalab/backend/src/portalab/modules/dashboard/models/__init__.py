"""Schema ``dashboard`` (specs/009-dashboard-widgets/data-model.md): one row per user (layout version,
starter and summary boundaries) and the user's widget instances (personal data class ``preference``).
Policies are configuration (020), applied on read — stored rows are never rewritten by a policy."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii


class DashboardBase(DeclarativeBase):
    metadata = schema_metadata("dashboard")


class UserDashboard(DashboardBase):
    __tablename__ = "user_dashboards"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    starter_applied_at: Mapped[datetime | None] = mapped_column(TZDateTime, info=pii("activity"))
    last_summary_seen_at: Mapped[datetime | None] = mapped_column(TZDateTime, info=pii("activity"))
    layout_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class WidgetInstance(DashboardBase):
    __tablename__ = "widget_instances"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'hidden')", name="status"),
        CheckConstraint("origin IN ('starter', 'user', 'policy_default')", name="origin"),
        CheckConstraint("w BETWEEN 1 AND 12 AND h BETWEEN 1 AND 12", name="size"),
        CheckConstraint("x >= 0 AND x + w <= 12 AND y >= 0", name="grid"),
        Index("ix_widget_instances_user_position", "user_id", "position"),
        Index("ix_widget_instances_user_grid", "user_id", "y", "x"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    widget_key: Mapped[str] = mapped_column(String(96), nullable=False, info=pii("preference", tombstone=""))
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active")
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # reading order, derived from (y, x)
    x: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )  # grid column (027)
    y: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")  # grid row
    w: Mapped[int] = mapped_column(Integer, nullable=False)
    h: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, info=pii("preference", tombstone={})
    )
    config_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
