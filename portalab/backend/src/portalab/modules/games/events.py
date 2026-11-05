"""Issue 265: the games' events, for the reward rules and the achievements the administrators set — a game
played to its end (alone, the day's puzzle or in a party: its score, whether it was won, the rank among how
many players) and one of the week's challenges completed (a game, a film, a book, an audiobook). Ids and
counters only, never titles. When a week or a month is over, each member placed on a game's board is told
their place once (``games.board_ranked``). Issue 356: a line of the month's media bingo completed
(``games.bingo_line``), and the full card (``games.bingo_card``)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:games"
PLAYED = "games.played"
CHALLENGE = "games.challenge_completed"
BOARD = "games.board_ranked"
BINGO_LINE = "games.bingo_line"
BINGO_CARD = "games.bingo_card"


class Played(BaseModel):
    session: str
    game: str  # poster, casting, synopsis, higher_lower, timeline, blindtest, memories, whowatched…
    mode: str  # solo, daily, party
    score: int
    correct: int
    rounds: int
    won: bool
    rank: int
    players: int


class ChallengeCompleted(BaseModel):
    week: str
    kind: str  # game, movie, book, audiobook
    target: int  # a game's minutes, the others' percent


class BoardRanked(BaseModel):
    game: str  # a game's key, « party » (parties won) or « challenge » (challenges completed)
    period: str  # week, month
    start: str  # the period's first day
    rank: int
    value: int  # the best score (the parties won, the challenges completed)
    players: int  # how many were on the board


class BingoLine(BaseModel):
    """Issue 356: a line of the month's media bingo completed (a row, a column, a diagonal)."""

    month: str  # its first day
    line: str  # row:0…3, col:0…3, diag:0|1
    lines: int  # how many lines of the card the member completed now


class BingoCard(BaseModel):
    """Issue 356: the month's media bingo card filled, every square."""

    month: str
    squares: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup, fields in (
        (
            PLAYED,
            Played,
            ("session",),
            frozenset({"game", "mode", "score", "correct", "rounds", "won", "rank", "players"}),
        ),
        (CHALLENGE, ChallengeCompleted, ("week", "kind"), frozenset({"kind", "target"})),
        (
            BOARD,
            BoardRanked,
            ("game", "period", "start"),
            frozenset({"game", "period", "rank", "value", "players"}),
        ),
        (BINGO_LINE, BingoLine, ("month", "line"), frozenset({"lines"})),
        (BINGO_CARD, BingoCard, ("month",), frozenset({"squares"})),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    dedup_fields=dedup,
                    retention_class="business",
                    visibility_class="private",
                    rewardable=fields,
                    aggregatable=fields,
                    automatable=True,
                )
            )
