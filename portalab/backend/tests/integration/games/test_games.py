"""Issue 265 — the games page: question after question alone (the answers kept on the server, the time its
own, the poster sharp only once answered), higher or lower until the first mistake, the day's title to find,
the memory of one's own cards, the parties played together by code, the week's retro challenge — each game
over told once to the reward rules, a member's games exported and erased with them."""

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select, text

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.media_core import (
    CARD_FACES,
    CARD_SOURCES,
    GAME_SOURCES,
    BingoCell,
    BingoTick,
    CardPerson,
    CardWork,
    PlayableGame,
    SeenWork,
)
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import FixedClock
from portalab.modules.games.cinemot import marks, word_of
from portalab.modules.games.common import GameClosed
from portalab.modules.games.models import GameSession, Party
from portalab.modules.games.module import GamesModule
from portalab.modules.games.participant import GamesParticipant
from portalab.modules.games.pool import NoTitles
from portalab.modules.games.settings import normalized
from portalab.modules.games.solo import DailyLimit, NotNow
from tests.authz_fixtures import INSERT_USER

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 60), (200, 30, 30)).save(out, "JPEG")
    return out.getvalue()


WORDS = (
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliett", "Kilo",
    "Lima", "Mike", "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "Xray", "Yankee", "Bingo", "Banjo",
)  # fmt: skip


def work(n: int, kind: str = "movie") -> CardWork:
    title = f"Film {WORDS[n]}" if kind == "movie" else f"Serie {WORDS[n]}"
    cast = [
        CardPerson(f"tmdb:{n}{i}", f"Actor{n} Person{i}", "cast", f"Hero{n}", i, f"/p{n}{i}.jpg")
        for i in range(4)
    ]
    return CardWork(
        object_id=uuid4(),
        kind=kind,
        title=title,
        year=1980 + n,
        countries=["FR"],
        languages=["French"],
        vote_count=5000,
        vote_average=5.0 + n * 0.3,
        tagline=None,
        poster=f"/poster{n}.jpg",
        backdrop=None,
        backdrops=[f"/scene{n}.jpg"],
        collection=None,
        people=cast,
        updated_at=NOW,
        available=True,
        facts={"runtime_min": 80 + n * 9},
        overview=f"Hero{n} meets Actor{n} Person1 in {title}: " + "a long story told about friendship. " * 4,
    )


class Sources:
    def __init__(self, works: list[CardWork]) -> None:
        self.items = works

    async def works(self, *, since: datetime | None = None) -> list[CardWork]:
        return self.items

    async def present(self) -> list[UUID]:
        return [w.object_id for w in self.items]

    async def work_of(self, object_id: UUID) -> UUID | None:
        return object_id

    async def season_of(self, object_id: UUID) -> int | None:
        return None

    async def image(self, ref: str, size: str) -> bytes:
        return _jpeg()

    async def role_images(self, person_ref: str) -> None:
        return None

    async def frames(self, object_id: UUID, at: Any) -> None:
        return None


class Games:
    def __init__(self, works: list[CardWork], game: PlayableGame) -> None:
        self.works = works
        self.game_ = game
        self.minutes: dict[UUID, float] = {}
        self.shares: dict[UUID, float] = {}  # how far each went in a film or a book
        self.history: dict[UUID, list[SeenWork]] = {}

    async def theme(self, object_id: UUID) -> bytes | None:
        return b"ID3-theme" if object_id in {w.object_id for w in self.works if w.kind == "series"} else None

    async def blurred(self, ref: str, radius: int) -> bytes:
        return _jpeg()

    async def titles(self, kind: str, *, limit: int) -> list[PlayableGame]:
        if kind == "game":
            return [self.game_]
        return [PlayableGame(uuid4(), f"A {kind}", None, None, kind=kind)] if kind != "audiobook" else []

    async def title(self, object_id: UUID) -> PlayableGame | None:
        return self.game_ if object_id == self.game_.object_id else None

    async def progress(self, kind: str, object_id: UUID, since: datetime) -> dict[UUID, float]:
        return dict(self.minutes) if kind == "game" else dict(self.shares)

    async def seen(self, user: UUID, *, limit: int) -> list[SeenWork]:
        return self.history.get(user, [])

    async def bingo_cells(
        self, *, year: int
    ) -> list[BingoCell]:  # issue 356: tests/integration/games/test_bingo
        return []

    async def bingo_ticks(
        self, keys: Any, since: datetime, until: datetime, *, user: UUID | None = None
    ) -> dict[UUID, dict[str, BingoTick]]:
        return {}


class Faces:
    async def faces(self, user: UUID, count: int) -> list[dict[str, Any]]:
        return [{"id": f"card-{i}", "name": f"Card {i}", "rarity": "rare"} for i in range(2)]


class Config:
    def __init__(self) -> None:
        self.sharing: set[UUID] = set()

    async def get(self, key: str, user_id: UUID | None = None) -> Any:
        if key == "games.whowatched.share":
            return SimpleNamespace(value=user_id in self.sharing)
        return SimpleNamespace(value=None)


class Events:
    def __init__(self) -> None:
        self.told: list[tuple[str, dict[str, Any], str | None]] = []

    async def publish(self, session: Any, event_type: str, metadata: Any = None, **kw: Any) -> Any:
        self.told.append((event_type, dict(metadata or {}), kw.get("dedup_key")))
        return SimpleNamespace(duplicate=False)


async def _users(database: Database, *names: str) -> list[UUID]:
    out = []
    async with database.unit_of_work() as uow:
        for name in names:
            user = uuid4()
            await uow.session.execute(INSERT_USER, {"id": user, "login": f"{name}{user.hex[:6]}"})
            out.append(user)
    return out


def _module(database: Database, clock: FixedClock | None = None) -> tuple[GamesModule, Games, Events, Config]:
    works = [work(n) for n in range(1, 13)] + [work(n, "series") for n in range(20, 26)]
    capabilities = new_registry()
    capabilities.provide(CARD_SOURCES, Sources(works), instance_ref="t", owner="test")
    games = Games(works, PlayableGame(uuid4(), "Super Metroid", "SNES", None))
    capabilities.provide(GAME_SOURCES, games, instance_ref="t", owner="test")
    capabilities.provide(CARD_FACES, Faces(), instance_ref="t", owner="test")
    config = Config()
    capabilities.provide(CONFIG, config, instance_ref="t", owner="test")
    events = Events()
    module = GamesModule(database, capabilities, clock=clock, events=events)  # type: ignore[arg-type]
    module.config.party.countdown_seconds = 0
    return module, games, events, config


async def _answer_of(database: Database, session_id: str) -> Any:
    async with database.session() as session:
        row = await session.get(GameSession, UUID(session_id))
        assert row is not None
        return row.state["questions"][row.state["at"]]["answer"]


async def test_a_game_alone_question_after_question(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    module, _, events, _ = _module(database)
    module.config.rounds["poster"] = module.config.round("poster").model_copy(update={"rounds": 3})
    view = await module.solo.start(zoe, "poster")
    assert view["round"] == 1 and view["rounds"] == 3 and view["question"]["image"]
    assert "answer" not in view["question"] and len(view["question"]["choices"]) == 4
    async with database.session() as session:
        started = await session.get(GameSession, UUID(view["id"]))
        assert started is not None  # a scene of the work, never its poster (its title is written on it)
        assert started.state["questions"][0]["media"]["poster"].startswith("/scene")
    blurred = await module.solo.media(zoe, UUID(view["id"]), "image")
    assert blurred[:2] == b"\xff\xd8"  # a JPEG, blurred by the server
    with pytest.raises(NotNow):
        await module.solo.next(zoe, UUID(view["id"]))  # answer first

    for round_ in range(3):
        right = await _answer_of(database, view["id"])
        given = right if round_ < 2 else "nope"
        view = await module.solo.answer(zoe, UUID(view["id"]), given)
        assert view["phase"] == "reveal" and view["result"]["answer"] == right
        assert view["result"]["correct"] is (round_ < 2)
        with pytest.raises(NotNow):
            await module.solo.answer(zoe, UUID(view["id"]), right)  # once per question
        view = await module.solo.next(zoe, UUID(view["id"]))
    assert view["status"] == "done" and view["correct"] == 2 and view["score"] >= 200
    async with database.session() as session:
        row = await session.get(GameSession, UUID(view["id"]))
        assert row is not None and "questions" not in row.state  # once over, only the results are kept
    assert [(t, m["game"], m["won"], m["mode"]) for t, m, _ in events.told] == [
        ("games.played", "poster", True, "solo")
    ]

    # the other games alone: each makes its questions from the library
    for game in ("casting", "synopsis", "timeline", "blindtest"):
        started = await module.solo.start(zoe, game)
        assert started["question"]["choices"], game
    synopsis = await module.solo.start(zoe, "synopsis")
    assert "Actor" not in synopsis["question"]["prompt"]["text"]  # its names hidden
    blind = await module.solo.start(zoe, "blindtest")
    assert await module.solo.media(zoe, UUID(blind["id"]), "audio") == b"ID3-theme"
    with pytest.raises(NoTitles):
        await module.solo.start(zoe, "memories")  # no history yet

    # an administrator switches a game off
    module.config.rounds["casting"] = module.config.round("casting").model_copy(update={"enabled": False})
    with pytest.raises(GameClosed):
        await module.solo.start(zoe, "casting")


async def test_higher_or_lower_until_the_first_mistake(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    module, _, events, _ = _module(database)
    view = await module.solo.start(zoe, "higher_lower")
    for _ in range(3):
        view = await module.solo.answer(zoe, UUID(view["id"]), await _answer_of(database, view["id"]))
        view = await module.solo.next(zoe, UUID(view["id"]))
    view = await module.solo.answer(zoe, UUID(view["id"]), "wrong")
    view = await module.solo.next(zoe, UUID(view["id"]))
    assert view["status"] == "done" and view["correct"] == 3 and view["rounds"] == 4
    assert events.told[0][1]["won"] is False  # ten in a row to win


async def test_the_day_s_title_to_find(database: Database) -> None:
    assert word_of("Le Pianiste") == "LE PIANISTE" and word_of("L'Été meurtrier") == "L ETE MEURTRIER"
    assert word_of("Rocky 4") is None
    assert marks("ALIEN", "LLAMA") == "acpaa" and marks("ALIEN", "ALIEN") == "ccccc"
    zoe, alex = await _users(database, "zoe", "alex")
    module, _, events, _ = _module(database, FixedClock(NOW))
    today = await module.cinemot.today(zoe)
    assert today["pattern"][0] in (4, 5) and today["status"] == "playing" and "answer" not in today
    assert (await module.cinemot.today(alex))["pattern"] == today["pattern"]  # the same for everyone
    with pytest.raises(ValidationFailed):
        await module.cinemot.guess(zoe, "ABC")
    async with database.session() as session:
        word = (await session.execute(text("SELECT payload->>'word' FROM games.puzzles"))).scalar_one()
    letters = len(word.replace(" ", ""))
    first = await module.cinemot.guess(zoe, "Z" * letters)
    assert first["guesses"][0]["marks"] == "a" * letters
    won = await module.cinemot.guess(zoe, word.lower())
    assert won["status"] == "done" and won["won"] and won["score"] == 500 and won["answer"]["word"] == word
    with pytest.raises(NotNow):
        await module.cinemot.guess(zoe, word)
    assert [(m["game"], m["mode"], m["won"]) for _, m, _ in events.told] == [("cinemot", "daily", True)]


async def test_the_memory_of_my_own_cards(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    module, _, events, _ = _module(database)
    module.config.memory.pairs = 4
    view = await module.solo.memory(zoe)
    assert len(view["board"]) == 8 and all(c["face"] is None for c in view["board"])
    async with database.session() as session:
        row = await session.get(GameSession, UUID(view["id"]))
        assert row is not None
        keys = [f["key"] for f in row.state["faces"]]
    assert sum(k.startswith("card:") for k in keys) == 4  # my two cards, then posters
    first = view["board"]
    view = await module.solo.flip(zoe, UUID(view["id"]), 0)
    wrong = next(i for i, k in enumerate(keys) if k != keys[0])
    view = await module.solo.flip(zoe, UUID(view["id"]), wrong)
    assert view["board"][0]["state"] == "open" and view["moves"] == 1
    for key in dict.fromkeys(keys):
        a, b = (i for i, k in enumerate(keys) if k == key)
        await module.solo.flip(zoe, UUID(view["id"]), a)
        view = await module.solo.flip(zoe, UUID(view["id"]), b)
    assert view["status"] == "done" and view["moves"] == 5 and view["score"] == 950
    assert first != view["board"] and events.told[0][1]["won"] is True


async def test_a_party_played_together(database: Database) -> None:
    host, zoe, alex = await _users(database, "host", "zoe", "alex")
    module, games, events, config = _module(database)
    opened = await module.parties.create(host, "poster", rounds=2, host_plays=False)
    code = opened["code"]
    assert opened["status"] == "lobby" and opened["is_host"] and not opened["playing"]
    with pytest.raises(NotNow):
        await module.parties.start(host, code)  # nobody plays yet
    await module.parties.join(zoe, code.lower())
    await module.parties.join(alex, code)
    started = await module.parties.start(host, code)
    assert started["status"] == "playing" and started["question"]["image"]
    assert (await module.parties.media(zoe, code, "image"))[:2] == b"\xff\xd8"
    for _ in range(2):
        async with database.session() as session:
            party = (await session.execute(select(Party).where(Party.code == code))).scalar_one()
            right = party.state["questions"][party.state["at"]]["answer"]
        view = await module.parties.answer(zoe, code, right)
        assert view["phase"] == "question" and view["given"] == right  # alex has not answered yet
        view = await module.parties.answer(alex, code, "wrong")
        assert view["phase"] == "reveal" and view["reveal"]["mine"]["correct"] is False
        view = await module.parties.next(host, code)
    assert view["status"] == "done"
    ranks = {p["id"]: p["rank"] for p in view["players"]}
    assert ranks == {str(zoe): 1, str(alex): 2}
    told = sorted((m["rank"], m["players"], m["won"], m["mode"]) for _, m, _ in events.told)
    assert told == [(1, 2, True, "party"), (2, 2, False, "party")]
    async with database.session() as session:
        live = await session.scalar(text("SELECT count(*) FROM core.live_event WHERE topic = 'games.party'"))
    assert live and live > 6  # every change told to the players and the host

    # « who watched it? »: only the players who agreed
    other = await module.parties.create(zoe, "whowatched")
    await module.parties.join(alex, other["code"])
    with pytest.raises(NoTitles):
        await module.parties.start(zoe, other["code"])
    config.sharing = {zoe, alex}
    games.history = {
        zoe: [SeenWork(uuid4(), "movie", "Alien", 1979, NOW)],
        alex: [SeenWork(uuid4(), "movie", "Heat", 1995, NOW)],
    }
    asked = await module.parties.start(zoe, other["code"])
    assert asked["question"]["prompt"]["title"] in ("Alien", "Heat")
    assert sorted(c["label"] for c in asked["question"]["choices"]) == [
        "?",
        "?",
    ]  # their names (no directory)


async def test_the_week_s_challenges(database: Database) -> None:
    zoe, alex = await _users(database, "zoe", "alex")
    module, games, events, _ = _module(database, FixedClock(NOW))
    games.minutes = {zoe: 31 * 60, alex: 10 * 60}
    games.shares = {alex: 0.95, zoe: 0.2}  # alex watched the film through; zoe a fifth of the book
    view = {c["kind"]: c for c in (await module.challenges.view(zoe))["items"]}
    assert set(view) == {"game", "movie", "book"}  # no audiobook in the library: no challenge
    game, movie, book = view["game"], view["movie"], view["book"]
    assert game["title"]["title"] == "Super Metroid" and game["target"] == 30 and game["unit"] == "minutes"
    assert game["done"] and game["mine"] == 31 and game["finishers"] == 1
    assert (
        movie["target"] == 90 and movie["unit"] == "percent" and not movie["done"] and movie["finishers"] == 1
    )
    assert book["target"] == 25 and book["mine"] == 20 and not book["done"]
    alex_view = {c["kind"]: c for c in (await module.challenges.view(alex))["items"]}
    assert alex_view["movie"]["done"] and not alex_view["game"]["done"]
    assert await module.challenges.check() == 0  # told already
    told = sorted((m["kind"], m["target"]) for t, m, _ in events.told if t == "games.challenge_completed")
    assert told == [("book", 25), ("game", 30), ("movie", 90)]  # each once (alex read the book too)
    assert (await module.boards.board(zoe, "challenge", "week"))["me"]["value"] == 1

    # the administrators switch one kind off, or draw the week's again
    module.config.challenge.kinds["book"] = module.config.challenge.of("book").model_copy(
        update={"enabled": False}
    )
    assert {c["kind"] for c in (await module.challenges.redraw("movie"))["items"]} == {"game", "movie"}


async def test_boards_settings_and_a_member_s_data(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    module, _, _, _ = _module(database)
    view = await module.solo.start(zoe, "timeline")
    order = await _answer_of(database, view["id"])
    for _ in range(view["rounds"]):
        view = await module.solo.answer(zoe, UUID(view["id"]), await _answer_of(database, view["id"]))
        view = await module.solo.next(zoe, UUID(view["id"]))
    assert view["status"] == "done" and view["correct"] == 3 and len(order) == 5
    board = await module.boards.board(zoe, "timeline", "week")
    assert board["me"]["value"] == view["score"] and board["entries"][0]["me"]
    hub = await module.boards.hub(zoe)
    assert {g["key"] for g in hub["games"]} >= {"poster", "cinemot", "memory", "challenge"}
    assert next(g for g in hub["games"] if g["key"] == "timeline")["best_week"] == view["score"]

    conf = normalized({"rounds": {"poster": {"rounds": 3}}, "unknown": 1})
    assert conf["rounds"]["poster"]["rounds"] == 3 and conf["rounds"]["casting"]["rounds"] == 8
    assert "unknown" not in conf

    exported = await GamesParticipant(database).export(zoe)
    assert [r.data["game"] for r in exported if r.category == "games.played"] == ["timeline"]
    await GamesParticipant(database).erase(zoe, "final")
    async with database.session() as session:
        assert not await session.scalar(
            select(func.count()).select_from(GameSession).where(GameSession.user_id == zoe)
        )


async def test_so_many_games_a_day(database: Database) -> None:
    (zoe,) = await _users(database, "zoe")
    clock = FixedClock(NOW)
    module, _, _, _ = _module(database, clock)
    module.config.rounds["poster"] = module.config.round("poster").model_copy(update={"per_day": 2})
    module.config.memory.per_day = 1
    await module.solo.start(zoe, "poster")  # left half-way: it counts all the same
    await module.solo.start(zoe, "poster")
    with pytest.raises(DailyLimit):
        await module.solo.start(zoe, "poster")
    await module.solo.start(zoe, "casting")  # each game its own count
    await module.solo.memory(zoe)
    with pytest.raises(DailyLimit):
        await module.solo.memory(zoe)
    hub = {g["key"]: g for g in (await module.boards.hub(zoe))["games"]}
    assert (hub["poster"]["per_day"], hub["poster"]["today"]) == (2, 2)
    assert (hub["casting"]["per_day"], hub["casting"]["today"]) == (5, 1)
    assert (hub["memory"]["per_day"], hub["memory"]["today"]) == (1, 1)
    assert "per_day" not in hub["cinemot"]

    clock.set(NOW + timedelta(days=1))  # a new day
    await module.solo.start(zoe, "poster")
    module.config.rounds["poster"] = module.config.round("poster").model_copy(update={"per_day": 0})
    for _ in range(3):  # no limit
        await module.solo.start(zoe, "poster")


async def test_the_boards_told_once_the_week_is_over(database: Database) -> None:
    """The week over, each member placed on a game's board is told their place, once — for the reward
    rules (« on the podium of the week »)."""
    zoe, max_ = await _users(database, "zoe", "max")
    last_week, _, _, _ = _module(database, FixedClock(NOW - timedelta(days=7)))
    scores = {}
    for user, right in ((zoe, True), (max_, False)):
        view = await last_week.solo.start(user, "timeline")
        for at in range(view["rounds"]):
            answer = await _answer_of(database, view["id"])
            if not right and at:
                answer = list(reversed(answer))
            view = await last_week.solo.answer(user, UUID(view["id"]), answer)
            view = await last_week.solo.next(user, UUID(view["id"]))
        scores[user] = view["score"]
    assert scores[zoe] > scores[max_] > 0

    module, _, events, _ = _module(database, FixedClock(NOW))
    assert await module.boards.close() == 2
    told = sorted(
        (m["rank"], m["game"], m["period"], m["start"], m["value"], m["players"], key)
        for t, m, key in events.told
        if t == "games.board_ranked"
    )
    assert [r[:6] for r in told] == [
        (1, "timeline", "week", "2026-10-19", scores[zoe], 2),
        (2, "timeline", "week", "2026-10-19", scores[max_], 2),
    ]
    assert told[0][6] == f"games.board_ranked:timeline:week:2026-10-19:{zoe}"  # once per member and week
    assert await module.boards.close() == 0  # already told
