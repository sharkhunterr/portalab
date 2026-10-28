"""Issue 265: what the games share — the configuration in force, the day in the economy's time zone (the
day's puzzle, the week's challenge), the games' events (``games.played``…) for the reward rules, and the
members' names."""

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.errors import Forbidden, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.modules.games.events import PLAYED
from portalab.modules.games.settings import GamesConfig

TIMEZONE = "economy.timezone"


class GameNotFound(NotFound):
    default_code = "games.not_found"
    default_title = "No such game"


class GameClosed(Forbidden):
    default_code = "games.closed"
    default_title = "This game is not open"


class Shared:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        config: Callable[[], GamesConfig],
        events: EventPublisher | None,
    ) -> None:
        self.capabilities = capabilities
        self.config = config
        self.events = events

    def open(self, game: str) -> GamesConfig:
        config = self.config()
        if game not in config.enabled_games():
            raise GameClosed("This game is switched off.")
        return config

    async def zone(self) -> ZoneInfo:
        providers = self.capabilities.system_providers(CONFIG)
        try:
            name = (await providers[0].provider.get(TIMEZONE)).value if providers else None
            return ZoneInfo(str(name)) if name else ZoneInfo("UTC")
        except Exception:
            return ZoneInfo("UTC")

    async def today(self, at: datetime) -> date:
        return at.astimezone(await self.zone()).date()

    async def week(self, at: datetime) -> tuple[date, datetime, datetime]:
        """The week's Monday, and when it starts and ends (UTC instants)."""
        zone = await self.zone()
        local = at.astimezone(zone).date()
        monday = local - timedelta(days=local.weekday())
        start = datetime.combine(monday, datetime.min.time(), zone)
        return monday, start, start + timedelta(days=7)

    async def shares(self, user: UUID) -> bool:
        """Whether a member agreed that « who watched it? » asks about them."""
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return False
        try:
            return bool((await providers[0].provider.get("games.whowatched.share", user_id=user)).value)
        except Exception:
            return False

    async def names(self, users: Iterable[UUID]) -> dict[UUID, str]:
        providers = self.capabilities.system_providers(DIRECTORY)
        out: dict[UUID, str] = {}
        for user in set(users):
            summary = await providers[0].provider.get_user_summary(user) if providers else None
            out[user] = (summary.display_name if summary else None) or "?"
        return out

    async def played(
        self,
        session: AsyncSession,
        user: UUID,
        *,
        key: str,
        game: str,
        mode: str,
        score: int,
        correct: int,
        rounds: int,
        won: bool,
        at: datetime,
        rank: int = 1,
        players: int = 1,
    ) -> None:
        """A game played to its end: what the reward rules and the achievements count."""
        if self.events is None:
            return
        payload: dict[str, Any] = {
            "session": key,
            "game": game,
            "mode": mode,
            "score": score,
            "correct": correct,
            "rounds": rounds,
            "won": won,
            "rank": rank,
            "players": players,
        }
        await self.events.publish(
            session,
            PLAYED,
            payload,
            occurred_at=at,
            subject=SubjectRef("user", str(user)),
            source="games",
            dedup_key=f"{PLAYED}:{key}",
        )
