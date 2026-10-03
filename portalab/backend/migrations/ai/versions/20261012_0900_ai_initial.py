"""ai schema — AI conversations, pending actions, usage

Revision ID: ai_0001
Revises:
Create Date: 2026-10-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ai_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("ai",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = ("pending_actions", "messages", "usage_daily", "conversations")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "ai"')
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        _user_fk("conversations", "user_id", "CASCADE"),
        schema="ai",
    )
    op.create_index(
        "ix_conversations_user", "conversations", ["user_id", "updated_at"], unique=False, schema="ai"
    )
    op.create_table(
        "usage_daily",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_usage_daily"),
        _user_fk("usage_daily", "user_id", "CASCADE"),
        schema="ai",
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("usage", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai.conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_messages_seq"),
        schema="ai",
    )
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("tool", sa.String(length=120), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("confirmed_at", TZ, nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'declined', 'expired', 'executed', 'failed')",
            name="ck_pending_actions_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai.conversations.id"],
            name="fk_pending_actions_conversation_id_conversations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pending_actions"),
        _user_fk("pending_actions", "user_id", "CASCADE"),
        schema="ai",
    )
    op.create_index(
        "ix_pending_actions_user", "pending_actions", ["user_id", "status"], unique=False, schema="ai"
    )


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table, schema="ai")
    op.execute('DROP SCHEMA IF EXISTS "ai"')
