"""Schema ``games`` (issue 265): the games a member played alone (each round's question and answer kept on
the server until it is played: nothing to read from the page), the day's puzzles, the parties played together
and their players, the week's challenge and who completed it."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id

OPEN = ("lobby", "playing")


class GamesBase(DeclarativeBase):
    metadata = schema_metadata("games")


class GameSession(GamesBase):
    """A game played alone — question after question, the day's title to find (``daily``: once a day) or the
    memory. ``state`` holds what the page must not know before it is played (the answers); once over, only
    each round's result is kept."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("mode IN ('solo', 'daily')", name="ck_sessions_mode"),
        CheckConstraint("status IN ('playing', 'done')", name="ck_sessions_status"),
        Index("ix_sessions_user_game", "user_id", "game", "finished_at"),
        Index("ix_sessions_game_finished", "game", "finished_at"),
        Index(
            "uq_sessions_daily",
            "user_id",
            "game",
            "day",
            unique=True,
            postgresql_where=text("day IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (DB), CASCADE: erased with them
    game: Mapped[str] = mapped_column(String(24), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="solo")
    day: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="playing")
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Puzzle(GamesBase):
    """The day's puzzle of a game (the title to find), the same for every member."""

    __tablename__ = "puzzles"

    game: Mapped[str] = mapped_column(String(24), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Party(GamesBase):
    """A game played together: joined by its code, run by its host, its rounds the same for every player."""

    __tablename__ = "parties"
    __table_args__ = (
        CheckConstraint("status IN ('lobby', 'playing', 'done', 'closed')", name="ck_parties_status"),
        Index(
            "uq_parties_open_code",
            "code",
            unique=True,
            postgresql_where=text("status IN ('lobby', 'playing')"),
        ),
        Index("ix_parties_status_updated", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    host_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (DB), CASCADE
    game: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="lobby")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PartyPlayer(GamesBase):
    """A player of a party: their score, their answer to each round, their rank once it is over."""

    __tablename__ = "party_players"
    __table_args__ = (Index("ix_party_players_user", "user_id"),)

    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.parties.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)  # FK identity.users (DB), CASCADE
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    joined_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Challenge(GamesBase):
    """One of the week's challenges: a game of the library to play some minutes, a film to watch through, a
    book or an audiobook to take some way (what the services and the portal tell)."""

    __tablename__ = "challenges"

    week: Mapped[date] = mapped_column(Date, primary_key=True)  # its Monday
    kind: Mapped[str] = mapped_column(String(12), primary_key=True)  # game, movie, book, audiobook
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(80))
    image_id: Mapped[UUID | None] = mapped_column()
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # its target: minutes, or a percent
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ChallengeDone(GamesBase):
    """A member who completed one of the week's challenges (once a week each)."""

    __tablename__ = "challenge_done"

    week: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)  # FK identity.users (DB), CASCADE
    at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
