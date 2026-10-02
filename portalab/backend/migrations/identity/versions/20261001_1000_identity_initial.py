"""identity initial schema — accounts, credentials, sessions, profiles, lifecycle (spec 002 T011)

Revision ID: identity_0001
Revises:
Create Date: 2026-10-01 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "identity_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("identity",)
depends_on: str | Sequence[str] | None = ("core_0003",)

STATES = "('pending_verification', 'active', 'inactive', 'suspended', 'pending_deletion', 'deleted')"
TZ = sa.DateTime(timezone=True)


def _users_fk(table: str, ondelete: str | None = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["identity.users.id"], name=f"fk_{table}_user_id_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "identity"')
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("login", sa.String(64)),
        sa.Column("login_display", sa.String(64)),
        sa.Column("display_name", sa.String(64)),
        sa.Column("display_name_key", sa.String(128)),
        sa.Column("email", sa.String(320)),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("state_before_deletion", sa.String(32)),
        sa.Column("transition_seq", sa.Integer(), nullable=False),
        sa.Column("state_changed_at", TZ, nullable=False),
        sa.Column("verified_at", TZ),
        sa.Column("last_sign_in_at", TZ),
        sa.Column("deletion_requested_at", TZ),
        sa.Column("deletion_due_at", TZ),
        sa.Column("deleted_at", TZ),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.CheckConstraint(f"state IN {STATES}", name="ck_users_state"),
        sa.CheckConstraint(
            f"state_before_deletion IS NULL OR state_before_deletion IN {STATES}", name="ck_users_prior"
        ),
        schema="identity",
    )
    op.create_index(
        "uq_users_login",
        "users",
        ["login"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("login IS NOT NULL"),
    )
    op.create_index(
        "uq_users_display_name_key",
        "users",
        ["display_name_key"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("display_name_key IS NOT NULL"),
    )
    op.create_index(
        "ix_users_state_state_changed_at", "users", ["state", "state_changed_at"], schema="identity"
    )
    op.create_index(
        "ix_users_deletion_due_at",
        "users",
        ["deletion_due_at"],
        schema="identity",
        postgresql_where=sa.text("state = 'pending_deletion'"),
    )

    op.create_table(
        "credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scheme", sa.String(16), nullable=False),
        sa.Column("hash", sa.String(512), nullable=False),
        sa.Column("params_version", sa.String(64), nullable=False),
        sa.Column("changed_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_credentials"),
        _users_fk("credentials"),
        schema="identity",
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("revoked_at", TZ),
        sa.Column("revoke_reason", sa.String(32)),
        sa.Column("user_agent_summary", sa.String(128)),
        sa.Column("ip_prefix", sa.String(64)),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        _users_fk("sessions"),
        sa.CheckConstraint(
            "revoke_reason IS NULL OR revoke_reason IN "
            "('logout', 'suspended', 'deleted', 'admin', 'password_change', 'rotated')",
            name="ck_sessions_reason",
        ),
        schema="identity",
    )
    op.create_index(
        "ix_sessions_user_id_active",
        "sessions",
        ["user_id"],
        schema="identity",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], schema="identity")

    op.create_table(
        "login_throttle",
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_start", TZ, nullable=False),
        sa.Column("blocked_until", TZ),
        sa.PrimaryKeyConstraint("key_hash", name="pk_login_throttle"),
        schema="identity",
    )

    op.create_table(
        "verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("consumed_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_verification_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_verification_tokens_token_hash"),
        _users_fk("verification_tokens"),
        sa.CheckConstraint("purpose IN ('verify')", name="ck_verification_tokens_purpose"),
        schema="identity",
    )
    op.create_index("ix_verification_tokens_user_id", "verification_tokens", ["user_id"], schema="identity")

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("avatar_blob_key", sa.String(128)),
        sa.Column("avatar_content_type", sa.String(32)),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_profiles"),
        _users_fk("profiles"),
        schema="identity",
    )
    op.create_index("ix_profiles_avatar_blob_key", "profiles", ["avatar_blob_key"], schema="identity")

    op.create_table(
        "profile_fields",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column("visibility_preference", sa.String(16), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "key", name="pk_profile_fields"),
        _users_fk("profile_fields"),
        sa.CheckConstraint(
            "visibility_preference IN ('public', 'community', 'leaderboard', 'private')",
            name="ck_profile_fields_visibility",
        ),
        schema="identity",
    )

    op.create_table(
        "account_state_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transition_seq", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(32)),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("received_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_account_state_history"),
        _users_fk("account_state_history", ondelete=None),
        schema="identity",
    )
    op.create_index(
        "ix_account_state_history_user_id_seq",
        "account_state_history",
        ["user_id", "transition_seq"],
        unique=True,
        schema="identity",
    )
    for statement in append_only_ddl("identity", "account_state_history"):
        op.execute(statement)

    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid()),
        sa.Column("requested_at", TZ, nullable=False),
        sa.Column("due_at", TZ, nullable=False),
        sa.Column("prior_state", sa.String(32), nullable=False),
        sa.Column("cancelled_at", TZ),
        sa.Column("cancelled_by", sa.Uuid()),
        sa.Column("finalized_at", TZ),
        sa.Column("saga_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id", name="pk_deletion_requests"),
        _users_fk("deletion_requests", ondelete=None),
        schema="identity",
    )
    op.create_index(
        "uq_deletion_requests_open",
        "deletion_requests",
        ["user_id"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("cancelled_at IS NULL AND finalized_at IS NULL"),
    )

    op.create_table(
        "onboarding_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(16), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("completed_at", TZ),
        sa.PrimaryKeyConstraint("user_id", "step", name="pk_onboarding_progress"),
        _users_fk("onboarding_progress"),
        sa.CheckConstraint(
            "step IN ('profile', 'interests', 'notifications', 'privacy', 'dashboard', 'discovery')",
            name="ck_onboarding_progress_step",
        ),
        schema="identity",
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", TZ, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("blob_key", sa.String(128)),
        sa.Column("completed_at", TZ),
        sa.Column("expires_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_export_jobs"),
        _users_fk("export_jobs"),
        sa.CheckConstraint(
            "status IN ('queued', 'ready', 'failed', 'expired')", name="ck_export_jobs_status"
        ),
        schema="identity",
    )
    op.create_index("ix_export_jobs_user_id", "export_jobs", ["user_id"], schema="identity")


def downgrade() -> None:
    for statement in drop_append_only_ddl("identity", "account_state_history"):
        op.execute(statement)
    for table in (
        "export_jobs",
        "onboarding_progress",
        "deletion_requests",
        "account_state_history",
        "profile_fields",
        "profiles",
        "verification_tokens",
        "login_throttle",
        "sessions",
        "credentials",
        "users",
    ):
        op.drop_table(table, schema="identity")
    op.execute('DROP SCHEMA IF EXISTS "identity"')
