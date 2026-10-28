"""Issue 265: the games' events, for the reward rules and the achievements the administrators set — a game
played to its end (alone, the day's puzzle or in a party: its score, whether it was won, the rank among how
many players) and one of the week's challenges completed (a game, a film, a book, an audiobook). Ids and
counters only, never titles."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:games"
PLAYED = "games.played"
CHALLENGE = "games.challenge_completed"


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


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup, fields in (
        (
            PLAYED,
            Played,
            ("session",),
            frozenset({"game", "mode", "score", "correct", "rounds", "won", "rank", "players"}),
        ),
        (CHALLENGE, ChallengeCompleted, ("week", "kind"), frozenset({"kind", "target"})),
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
