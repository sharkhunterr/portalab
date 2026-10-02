"""Schema ``shell`` (specs/004-portal-core-shell/data-model.md): diagnostics of rejected navigation
contributions and the navigation epochs (cache invalidation across processes). No personal data."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class ShellBase(DeclarativeBase):
    metadata = schema_metadata("shell")


class ContributionError(ShellBase):
    __tablename__ = "contribution_errors"
    __table_args__ = (
        CheckConstraint("reason IN ('schema', 'duplicate', 'conflict', 'runtime')", name="reason"),
        UniqueConstraint("owner", "key", "reason", name="uq_contribution_errors"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str] = mapped_column(String(512), nullable=False, info=not_personal("validation message"))
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class Epoch(ShellBase):
    """``permission`` and ``module`` epochs: bumped when rights or enablement change anywhere."""

    __tablename__ = "epochs"

    name: Mapped[str] = mapped_column(String(32), primary_key=True, info=not_personal("epoch name"))
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
