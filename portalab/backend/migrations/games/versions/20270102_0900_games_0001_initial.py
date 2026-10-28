"""games schema — the games a member played alone, the day's puzzles, the parties and their players, the
week's challenge and who completed it (issue 265)

Revision ID: games_0001
Revises:
Create Date: 2026-10-28 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "games_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("games",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)


def _user(table: str, column: str = "user_id") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}", ondelete="CASCADE"
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "games"')
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("game", sa.String(24), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("day", sa.Date(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ, nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        _user("sessions"),
        sa.CheckConstraint("mode IN ('solo', 'daily')", name="ck_sessions_mode"),
        sa.CheckConstraint("status IN ('playing', 'done')", name="ck_sessions_status"),
        schema="games",
    )
    op.create_index("ix_sessions_user_game", "sessions", ["user_id", "game", "finished_at"], schema="games")
    op.create_index("ix_sessions_game_finished", "sessions", ["game", "finished_at"], schema="games")
    op.create_index(
        "uq_sessions_daily",
        "sessions",
        ["user_id", "game", "day"],
        unique=True,
        schema="games",
        postgresql_where=sa.text("day IS NOT NULL"),
    )
    op.create_table(
        "puzzles",
        sa.Column("game", sa.String(24), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("game", "day", name="pk_puzzles"),
        schema="games",
    )
    op.create_table(
        "parties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("game", sa.String(24), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_parties"),
        _user("parties", "host_id"),
        sa.CheckConstraint("status IN ('lobby', 'playing', 'done', 'closed')", name="ck_parties_status"),
        schema="games",
    )
    op.create_index(
        "uq_parties_open_code",
        "parties",
        ["code"],
        unique=True,
        schema="games",
        postgresql_where=sa.text("status IN ('lobby', 'playing')"),
    )
    op.create_index("ix_parties_status_updated", "parties", ["status", "updated_at"], schema="games")
    op.create_table(
        "party_players",
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("joined_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("party_id", "user_id", name="pk_party_players"),
        sa.ForeignKeyConstraint(
            ["party_id"], ["games.parties.id"], name="fk_party_players_party", ondelete="CASCADE"
        ),
        _user("party_players"),
        schema="games",
    )
    op.create_index("ix_party_players_user", "party_players", ["user_id"], schema="games")
    op.create_table(
        "challenges",
        sa.Column("week", sa.Date(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(80), nullable=True),
        sa.Column("image_id", sa.Uuid(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("week", name="pk_challenges"),
        schema="games",
    )
    op.create_table(
        "challenge_done",
        sa.Column("week", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("week", "user_id", name="pk_challenge_done"),
        _user("challenge_done"),
        schema="games",
    )


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "games" CASCADE')
