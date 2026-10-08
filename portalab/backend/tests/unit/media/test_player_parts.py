"""027 (#2) — the player's stream tickets (signed, per member, expiring) and subtitle feeds (cues kept with
their times, restarted after a jump outside what was gathered)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import pytest

from portalab.capabilities.media import StreamOptions, SubtitleCue
from portalab.modules.media.player.subtitles import SubtitleFeed, SubtitleFeeds
from portalab.modules.media.player.tickets import Ticket, TicketInvalid, read, sign

KEY = b"k" * 32
NOW = datetime(2026, 10, 8, 20, tzinfo=UTC)
ZOE, MAX = UUID(int=1), UUID(int=2)


def _ticket(**changes: object) -> Ticket:
    values: dict[str, object] = {
        "user": ZOE,
        "service": UUID(int=9),
        "account": "7",
        "item": "m1",
        "session": "abc",
        "options": StreamOptions(quality="8m", subtitle="s1"),
        "duration_s": 100.0,
        "expires": int(NOW.timestamp()) + 60,
    }
    values.update(changes)
    return Ticket(**values)  # type: ignore[arg-type]


def test_ticket_round_trip_and_refusals() -> None:
    token = sign(KEY, _ticket())
    assert read(KEY, token, user=ZOE, now=NOW) == _ticket()
    with pytest.raises(TicketInvalid):
        read(KEY, token, user=MAX, now=NOW)  # someone else's
    with pytest.raises(TicketInvalid):
        read(b"x" * 32, token, user=ZOE, now=NOW)  # another portal's key
    payload, mac = token.split(".")
    with pytest.raises(TicketInvalid):
        read(KEY, f"{payload[:-2]}AA.{mac}", user=ZOE, now=NOW)  # tampered
    with pytest.raises(TicketInvalid):
        read(KEY, sign(KEY, _ticket(expires=int(NOW.timestamp()) - 1)), user=ZOE, now=NOW)
    with pytest.raises(TicketInvalid):
        read(KEY, "garbage", user=ZOE, now=NOW)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_feed_gathers_cues_and_restarts_after_a_jump() -> None:
    opened: list[int] = []
    cues = [SubtitleCue(10, 12, "a"), SubtitleCue(20, 22, "b"), SubtitleCue(500, 502, "far")]

    @asynccontextmanager
    async def opener() -> AsyncIterator[AsyncIterator[SubtitleCue]]:
        opened.append(len(opened))

        async def feed() -> AsyncIterator[SubtitleCue]:
            for cue in cues[:2] if len(opened) == 1 else cues[2:]:
                yield cue
            await asyncio.sleep(3600)

        yield feed()

    clock = _Clock()
    feed = SubtitleFeed(opener, clock=clock)
    feed.ensure(0)
    await asyncio.sleep(0.01)
    assert [c.text for c in feed.window(0)] == ["a", "b"]
    assert [c.text for c in feed.window(15)] == ["b"]  # the ones already said are left out
    feed.ensure(30)  # still within reach: the same feed
    assert len(opened) == 1
    feed.ensure(495, seek=True)  # a jump far ahead: the service restarts the subtitles from there
    await asyncio.sleep(0.01)
    assert len(opened) == 2 and [c.text for c in feed.window(495)] == ["far"]
    assert [c.text for c in feed.window(9)] == ["a", "b"]  # what was gathered before is kept
    feed.close()


async def test_feeds_close_when_idle() -> None:
    clock = _Clock()

    @asynccontextmanager
    async def opener() -> AsyncIterator[AsyncIterator[SubtitleCue]]:
        async def feed() -> AsyncIterator[SubtitleCue]:
            await asyncio.sleep(3600)
            yield SubtitleCue(0, 1, "never")

        yield feed()

    feeds = SubtitleFeeds(clock=clock)
    first = feeds.get("s1", opener)
    first.ensure(0)
    assert feeds.get("s1", opener) is first
    clock.now += 2000  # a quarter of an hour of silence and more
    feeds.get("s2", opener)
    assert "s1" not in feeds.feeds
    await asyncio.sleep(0)
    assert first.task is None
    feeds.close("s2")
