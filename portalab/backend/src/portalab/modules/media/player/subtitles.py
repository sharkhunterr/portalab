"""The text subtitles of a stream (027, #2), gathered from the service's subtitle feed.

The service hands the selected subtitle out as its transcoder reaches it, from where the stream stands. A
feed reads it in the background and keeps the cues (with their absolute times), so the player asks for
« the cues around this moment »; after a jump outside what was gathered, the feed restarts from there.
Feeds live in the process that relays the stream and close after a quarter of an hour of silence.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

from portalab.capabilities.media import SubtitleCue

log = logging.getLogger(__name__)
MAX_CUES = 20_000
IDLE_S = 900.0
AHEAD_S = 45.0  # how far past what was gathered the player may be before the feed restarts
RESTART_PAUSE_S = 10.0

Opener = Callable[[], AbstractAsyncContextManager[AsyncIterator[SubtitleCue]]]


class SubtitleFeed:
    def __init__(self, opener: Opener, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.opener = opener
        self.clock = clock
        self.cues: dict[tuple[float, float, str], SubtitleCue] = {}
        self.task: asyncio.Task[None] | None = None
        self.origin = 0.0
        self.reach = 0.0
        self.restarted = 0.0
        self.touched = clock()

    def _running(self) -> bool:
        return self.task is not None and not self.task.done()

    def _covered(self, at: float) -> bool:
        # the transcoder runs at least as fast as the film: silence still moves the feed forward
        progressed = self.origin + (self.clock() - self.restarted)
        return self.origin - 1 <= at <= max(self.reach, progressed) + AHEAD_S

    def ensure(self, at: float, *, seek: bool = False) -> None:
        self.touched = self.clock()
        if self._running() and self._covered(at):
            return
        if self._running() and not seek and self.clock() - self.restarted < RESTART_PAUSE_S:
            return
        self.close()
        self.origin = self.reach = max(at, 0.0)
        self.restarted = self.clock()
        self.task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            async with self.opener() as cues:
                async for cue in cues:
                    if len(self.cues) < MAX_CUES:
                        self.cues[(cue.start_s, cue.end_s, cue.text)] = cue
                    self.reach = max(self.reach, cue.end_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the service closed the feed: the next request restarts it
            log.info("subtitle feed ended", extra={"fields": {"error": type(exc).__name__}})

    def window(self, at: float, ahead: float = 120.0) -> list[SubtitleCue]:
        return sorted(
            (c for c in self.cues.values() if c.end_s >= at - 1 and c.start_s <= at + ahead),
            key=lambda c: (c.start_s, c.end_s),
        )

    def close(self) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()
        self.task = None


class SubtitleFeeds:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.feeds: dict[str, SubtitleFeed] = {}

    def get(self, key: str, opener: Opener) -> SubtitleFeed:
        now = self.clock()
        for stale in [k for k, f in self.feeds.items() if now - f.touched > IDLE_S]:
            self.feeds.pop(stale).close()
        feed = self.feeds.get(key)
        if feed is None:
            feed = self.feeds[key] = SubtitleFeed(opener, clock=self.clock)
        return feed

    def close(self, key: str) -> None:
        feed = self.feeds.pop(key, None)
        if feed is not None:
            feed.close()
