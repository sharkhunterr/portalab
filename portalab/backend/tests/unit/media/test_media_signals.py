"""Issue 122 — the plays under way as service signals, read through guarded providers."""


async def test_media_plays_read_through_a_guarded_provider() -> None:
    """A guarded provider answers ``Available(value=…)``; a failure is unknown, never « nobody plays »."""
    from datetime import UTC, datetime

    from portalab.capabilities.media import SourcePlayback
    from portalab.capabilities.results import Available, Unavailable
    from portalab.capabilities.service_signals import SignalRegistry
    from portalab.modules.media.signals import register_media_signals

    registry = SignalRegistry()
    register_media_signals(registry)
    sessions = [
        SourcePlayback("1", "playing", "movie", "Sissi"),
        SourcePlayback("2", "paused", "episode", "Dark"),
    ]

    class Guarded:
        def __init__(self, result: object) -> None:
            self.result = result

        async def now_playing(self) -> object:
            return self.result

    ok = Guarded(Available(sessions, as_of=datetime.now(UTC)))
    down = Guarded(Unavailable(detail="down"))
    plays, paused, titles = (
        registry.get(k) for k in ("media.plays", "media.plays_paused", "media.playing_titles")
    )
    assert plays and paused and titles
    assert await plays.read("plex", ok) == 2 and await paused.read("plex", ok) == 1
    assert await titles.read("plex", ok) == "Dark, Sissi"
    assert await plays.read("plex", down) is None
