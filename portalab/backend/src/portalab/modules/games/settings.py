"""Games settings (issue 265), declared to Administration: one record, ``games.config`` — the page switched on
or off, the titles the games draw from, each game's rounds, time and choices (or its own figures), the
parties, the week's challenge — and each member's consent to « who watched it? ». The rewards are the reward
rules' (``games.played``, ``games.challenge_completed``): set where every other reward is."""

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:games"
KEY = "games.config"
SHARE = "games.whowatched.share"

# the games played question after question — alone, and in a party for most
ROUND_GAMES = (
    "poster",
    "casting",
    "synopsis",
    "higher_lower",
    "timeline",
    "blindtest",
    "memories",
    "whowatched",
)
SOLO_ONLY = ("memories",)  # my own history: a party cannot share it
PARTY_ONLY = ("whowatched",)  # whose history: the players'
GAMES = (*ROUND_GAMES, "cinemot", "memory", "challenge")


class RoundGame(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    rounds: int = Field(default=6, ge=1, le=50)  # higher or lower: the longest streak played
    seconds: int = Field(default=20, ge=5, le=180)
    choices: int = Field(default=4, ge=2, le=8)  # the timeline: how many titles to put in order
    per_day: int = Field(default=5, ge=0, le=100)  # games a member may start alone each day (0: no limit)


DEFAULT_ROUNDS: dict[str, RoundGame] = {
    "poster": RoundGame(rounds=6, seconds=25),
    "casting": RoundGame(rounds=8, seconds=20),
    "synopsis": RoundGame(rounds=6, seconds=30),
    "higher_lower": RoundGame(rounds=30, seconds=12, choices=2),
    "timeline": RoundGame(rounds=3, seconds=45, choices=5),
    "blindtest": RoundGame(rounds=6, seconds=30),
    "memories": RoundGame(rounds=6, seconds=20),
    "whowatched": RoundGame(rounds=8, seconds=15),
}


KINDS: tuple[Literal["movie", "series"], ...] = ("movie", "series")


class Library(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kinds: list[Literal["movie", "series"]] = Field(default_factory=lambda: list(KINDS))
    min_votes: int = Field(default=100, ge=0, le=100_000)  # known enough to be guessed
    available_only: bool = True


class Cinemot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    tries: int = Field(default=6, ge=3, le=10)
    min_letters: int = Field(default=5, ge=3, le=20)
    max_letters: int = Field(default=12, ge=4, le=30)


class Memory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    pairs: int = Field(default=8, ge=4, le=15)
    own_cards: bool = True  # the member's own cards (the posters when they own too few)
    per_day: int = Field(default=5, ge=0, le=100)


CHALLENGE_KINDS = ("game", "movie", "book", "audiobook")


class KindChallenge(BaseModel):
    """One of the week's challenges: a game to play ``target`` minutes; a film, a book or an audiobook to
    take to ``target`` percent (a film to its end: 90)."""

    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    target: int = Field(default=30, ge=1, le=600)
    item: str | None = Field(default=None, max_length=40)  # a title pinned by the administrators (its id)


DEFAULT_CHALLENGES: dict[str, KindChallenge] = {
    "game": KindChallenge(target=30),
    "movie": KindChallenge(target=90),
    "book": KindChallenge(target=25),
    "audiobook": KindChallenge(target=25),
}


class Challenge(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    kinds: dict[str, KindChallenge] = Field(default_factory=dict)

    def of(self, kind: str) -> KindChallenge:
        return self.kinds.get(kind) or DEFAULT_CHALLENGES[kind]

    def open(self) -> list[str]:
        return [k for k in CHALLENGE_KINDS if self.enabled and self.of(k).enabled]


class Party(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    max_players: int = Field(default=12, ge=2, le=50)
    reveal_seconds: int = Field(default=6, ge=2, le=30)
    countdown_seconds: int = Field(default=3, ge=0, le=10)


class GamesConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    library: Library = Field(default_factory=Library)
    rounds: dict[str, RoundGame] = Field(default_factory=dict)
    cinemot: Cinemot = Field(default_factory=Cinemot)
    memory: Memory = Field(default_factory=Memory)
    challenge: Challenge = Field(default_factory=Challenge)
    party: Party = Field(default_factory=Party)

    def round(self, game: str) -> RoundGame:
        return self.rounds.get(game) or DEFAULT_ROUNDS[game]

    def per_day(self, game: str) -> int:
        """How many games of it a member may start alone each day (0: as many as they like)."""
        if game == "memory":
            return self.memory.per_day
        return self.round(game).per_day if game in ROUND_GAMES else 0

    def enabled_games(self) -> list[str]:
        if not self.enabled:
            return []
        out = [g for g in ROUND_GAMES if self.round(g).enabled]
        out += [g for g in ("cinemot", "memory", "challenge") if getattr(self, g).enabled]
        return out


def normalized(value: dict[str, Any]) -> dict[str, Any]:
    """Every game present with its figures (a game missing takes its defaults), unknown keys dropped."""
    config = GamesConfig.model_validate(value)
    config.rounds = {g: config.round(g) for g in ROUND_GAMES}
    config.challenge.kinds = {k: config.challenge.of(k) for k in CHALLENGE_KINDS}
    return config.model_dump(mode="json")


def config_of(value: Any) -> GamesConfig:
    try:
        return GamesConfig.model_validate(value or {})
    except ValueError:
        return GamesConfig()


Schema = Annotated[dict[str, Any], AfterValidator(normalized)]


def declare_games_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    if KEY not in known:
        declare(
            scope="global",
            key=KEY,
            schema=Schema,
            default=normalized({}),
            owner=OWNER,
            description=(
                "The games page: switched on or off; the titles its games draw from (kinds, votes, present "
                "only); each game's rounds, seconds, choices and games a day; the day's title to find "
                "(tries, letters); the memory (pairs, the member's own cards, games a day); the week's "
                "challenges (a game's minutes, a film's, a book's, an audiobook's percent; a title pinned); "
                "the parties (players, reveal and countdown seconds). Rewards: the reward rules of "
                "games.played and games.challenge_completed."
            ),
        )
    if SHARE not in known:
        declare(
            scope="global",
            key=SHARE,
            schema=bool,
            default=False,
            user_overridable=True,
            owner=OWNER,
            description="« Who watched it? »: the games may ask the other players what you watched.",
        )


declare_games_settings()
