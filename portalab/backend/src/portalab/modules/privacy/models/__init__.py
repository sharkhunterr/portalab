"""Schema ``privacy`` (specs/021-privacy-data-lifecycle/data-model.md).

``visibility_policies`` rows are history: a policy is active while ``removed_at`` is null and ``ends_at``
has not passed; at most one unremoved row per (subject, datum class) — a null subject is a class-wide
policy. ``retention_runs`` is append-only.

027 — terms of use: ``terms_versions`` is the published history (append-only: a published version is never
changed, a new one supersedes it); ``terms_acceptances`` records which version each member accepted, when;
``terms_settings`` (one row) whether the administrators ask for them at all — optional: with nothing
published, or the switch off, the portal asks nothing.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

MODES: tuple[str, ...] = ("user_choice", "force_visible", "force_private")
LEVELS: tuple[str, ...] = ("public", "community", "leaderboard", "private")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class PrivacyBase(DeclarativeBase):
    metadata = schema_metadata("privacy")


class VisibilityPolicy(PrivacyBase):
    __tablename__ = "visibility_policies"
    __table_args__ = (
        CheckConstraint(_in("mode", MODES), name="mode"),
        CheckConstraint(f"level IS NULL OR {_in('level', LEVELS)}", name="level"),
        CheckConstraint(
            "(mode = 'user_choice' AND level IS NULL) OR (mode = 'force_private' AND level = 'private') "
            "OR (mode = 'force_visible' AND level IN ('public', 'community', 'leaderboard'))",
            name="mode_level",
        ),
        Index(
            "uq_visibility_policies_active",
            "subject_user_id",
            "datum_class",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    subject_user_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (DB); null = class-wide
    datum_class: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    level: Mapped[str | None] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    set_by: Mapped[UUID | None] = mapped_column()
    set_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    removed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    removed_by: Mapped[UUID | None] = mapped_column()


class RetentionRun(PrivacyBase):
    __tablename__ = "retention_runs"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(128), nullable=False)
    data_class: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    rows_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    cutoff: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    run_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(String(256))


class TermsVersion(PrivacyBase):
    __tablename__ = "terms_versions"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("document title"))
    summary: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    # a correction that changes nothing for members (a typo) does not ask them to accept again
    requires_acceptance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    published_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class TermsAcceptance(PrivacyBase):
    __tablename__ = "terms_acceptances"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)  # FK identity.users (DB), CASCADE
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    accepted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class TermsSettings(PrivacyBase):
    __tablename__ = "terms_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
