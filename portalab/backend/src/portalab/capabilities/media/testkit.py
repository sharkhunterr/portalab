"""Fake media providers and capability conformance kits (spec 024 T004, 001 rule).

A connector proves it implements the media capabilities with::

    class TestPlexPlayback(PlaybackContractKit):
        async def make_provider(self) -> MediaPlayback: ...      # bound to a test service
        async def start_session(self, provider) -> None: ...      # make the source report one session

    class TestPlexLibrary(LibraryRecordKit):
        async def records(self) -> list[SourceRecord]: ...       # what ``sync`` yields for a sample library

The fakes below are what Media's own tests use; they simulate outages, timeouts and verification.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import (
    REQUEST_STATES,
    LibraryPayload,
    MediaPlayback,
    PlayableItem,
    RequestPayload,
    RequestService,
    ResumePoint,
    SourceHistoryItem,
    SourcePlayback,
    SourceRequest,
    StreamBody,
    StreamOptions,
    StreamStart,
    StreamTrack,
    StreamVersion,
    SubtitleCue,
)
from portalab.capabilities.results import ProviderAuthError, ProviderNotFound

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND"
    b"\xaeB`\x82"
)


@dataclass
class FakeLibrary:
    """``media.library`` provider: serves images by opaque ref (records come through the sink)."""

    images: dict[str, bytes] = field(default_factory=dict)
    down: bool = False
    fetched: list[str] = field(default_factory=list)

    async def fetch_image(self, ref: str) -> bytes:
        if self.down:
            raise ConnectionError("fake library unreachable")
        self.fetched.append(ref)
        if ref not in self.images:
            raise LookupError(ref)
        return self.images[ref]


@dataclass
class FakePlayback:
    sessions: dict[str, SourcePlayback] = field(default_factory=dict)
    history: list[SourceHistoryItem] = field(default_factory=list)
    down: bool = False
    hang: bool = False
    codes: dict[str, str] = field(default_factory=dict)  # external user → verification code

    def play(self, key: str, **values: Any) -> None:
        current = self.sessions.get(key)
        base: dict[str, Any] = (
            {
                "session_key": key,
                "state": current.state,
                "kind": current.kind,
                "title": current.title,
                "external_user_id": current.external_user_id,
                "item_external_id": current.item_external_id,
                "ids": dict(current.ids),
                "position_s": current.position_s,
                "duration_s": current.duration_s,
                "device": current.device,
            }
            if current
            else {"session_key": key, "state": "playing", "kind": "movie", "title": "?"}
        )
        base.update(values)
        self.sessions[key] = SourcePlayback(**base)

    def stop(self, key: str) -> None:
        self.sessions.pop(key, None)

    async def _answer(self) -> None:
        if self.hang:
            await asyncio.sleep(3600)
        if self.down:
            raise ConnectionError("fake playback source unreachable")

    async def now_playing(self) -> Sequence[SourcePlayback]:
        await self._answer()
        return list(self.sessions.values())

    async def recent_history(self, since: datetime) -> Sequence[SourceHistoryItem]:
        await self._answer()
        return [item for item in self.history if item.occurred_at >= since]

    async def verify_user(self, external_user_id: str, proof: str) -> bool:
        await self._answer()
        return self.codes.get(external_user_id) == proof


@dataclass
class FakeRequests:
    submitted: list[dict[str, Any]] = field(default_factory=list)
    states: dict[str, str] = field(default_factory=dict)
    down: bool = False
    initial_state: str = "pending"

    async def submit(
        self, ids: Mapping[str, str], kind: str, title: str, requester: str | None, **options: Any
    ) -> SourceRequest:
        if self.down:
            raise ConnectionError("fake request service unreachable")
        external = f"req-{len(self.submitted) + 1}"
        self.submitted.append(
            {"ids": dict(ids), "kind": kind, "title": title, "requester": requester, **options}
        )
        self.states[external] = self.initial_state
        return SourceRequest(external, self.initial_state, f"source:{self.initial_state}")  # type: ignore[arg-type]

    async def status(self, external_request_id: str) -> SourceRequest:
        if self.down:
            raise ConnectionError("fake request service unreachable")
        state = self.states[external_request_id]
        return SourceRequest(external_request_id, state, f"source:{state}")  # type: ignore[arg-type]

    async def cancel(self, external_request_id: str) -> None:
        self.states[external_request_id] = "cancelled"

    async def decide(self, external_request_id: str, approve: bool) -> SourceRequest:
        """#4: an administrator's decision taken from the portal."""
        if self.down:
            raise ConnectionError("fake request service unreachable")
        state = "approved" if approve else "declined"
        self.states[external_request_id] = state
        return SourceRequest(external_request_id, state, f"source:{state}")  # type: ignore[arg-type]


def library_record(
    external_id: str,
    *,
    kind: str = "movie",
    at: datetime | None = None,
    removed: bool = False,
    **payload: Any,
) -> SourceRecord:
    return SourceRecord(
        source_system="fake",
        external_id=external_id,
        kind=kind,
        payload=payload,
        observed_at=at or datetime(2026, 1, 1, tzinfo=UTC),
        removed=removed,
    )


# --- conformance kits ---------------------------------------------------------------------------------------
class LibraryRecordKit:
    """Records a ``media.library`` connector yields: valid payloads, strong ids, no secrets in refs."""

    async def records(self) -> list[SourceRecord]:
        raise NotImplementedError

    async def test_payloads_validate(self) -> None:
        records = await self.records()
        assert records, "the kit needs at least one record"
        for record in records:
            if not record.removed:
                LibraryPayload.model_validate(dict(record.payload))

    async def test_no_credentials_in_payloads(self) -> None:
        for record in await self.records():
            text = repr(dict(record.payload)).lower()
            assert "token=" not in text and "api_key" not in text and "x-plex-token" not in text

    async def test_external_ids_are_unique(self) -> None:
        ids = [r.external_id for r in await self.records()]
        assert len(ids) == len(set(ids))


class PlaybackContractKit:
    async def make_provider(self) -> MediaPlayback:
        raise NotImplementedError

    async def start_session(self, provider: Any) -> None:
        raise NotImplementedError

    async def test_reports_normalized_sessions(self) -> None:
        provider = await self.make_provider()
        await self.start_session(provider)
        sessions = list(await provider.now_playing())
        assert sessions
        for session in sessions:
            assert isinstance(session, SourcePlayback)
            assert session.state in ("playing", "paused", "buffering", "stopped")
            assert session.position_s >= 0 and session.session_key

    async def test_history_is_typed(self) -> None:
        provider = await self.make_provider()
        for item in await provider.recent_history(datetime(2000, 1, 1, tzinfo=UTC)):
            assert isinstance(item, SourceHistoryItem) and item.occurred_at.tzinfo is not None


class RequestServiceContractKit:
    async def make_provider(self) -> RequestService:
        raise NotImplementedError

    async def test_submit_then_status(self) -> None:
        provider = await self.make_provider()
        answer = await provider.submit({"tmdb": "603"}, "movie", "The Matrix", None)
        assert answer.state in REQUEST_STATES and answer.external_request_id
        again = await provider.status(answer.external_request_id)
        assert again.external_request_id == answer.external_request_id and again.state in REQUEST_STATES

    async def test_request_records_validate(self) -> None:
        RequestPayload.model_validate({"title": "x", "kind": "movie", "state": "pending"})


# --- 027 (#2): the portal's player ----------------------------------------------------------------------
@dataclass
class FakeStreaming:
    """``media.streaming``: one film (``m1``) with a text and an image subtitle; account ``denied`` has no
    access. Records every call as ``(account, operation, details)``."""

    calls: list[tuple[str | None, str, Any]] = field(default_factory=list)
    resume: list[ResumePoint] = field(default_factory=list)
    cues: list[SubtitleCue] = field(
        default_factory=lambda: [SubtitleCue(1.0, 2.5, "Hello"), SubtitleCue(300.0, 302.0, "Later")]
    )

    def channel(self, external_user_id: str | None) -> "FakeChannel":
        return FakeChannel(self, external_user_id)


class FakeChannel:
    def __init__(self, owner: FakeStreaming, account: str | None) -> None:
        self.owner, self.account = owner, account

    def _check(self, external_id: str) -> None:
        if self.account == "denied":
            raise ProviderAuthError("no access")
        if external_id not in ("m1", "e2"):
            raise ProviderNotFound("no such item")

    async def playable(self, external_id: str) -> PlayableItem:
        self._check(external_id)
        self.owner.calls.append((self.account, "playable", external_id))
        version = StreamVersion(
            index=0,
            label="1080p · H.264",
            resolution="1080p",
            audio=(StreamTrack("a1", "audio", "English", language="en", selected=True),),
            subtitles=(
                StreamTrack("s1", "subtitle", "Français", language="fr"),
                StreamTrack("s2", "subtitle", "PGS", codec="pgs", text=False),
            ),
        )
        return PlayableItem(
            external_id=external_id,
            kind="movie",
            title="Film",
            duration_s=6000.0,
            resume_s=60.0,
            versions=(version,),
        )

    async def start(self, external_id: str, options: StreamOptions, session: str) -> StreamStart:
        self._check(external_id)
        self.owner.calls.append((self.account, "start", options))
        burn = options.subtitle == "s2" or (options.subtitle is not None and options.burn)
        return StreamStart(
            session=session,
            playlist=f"session/{session}/base/index.m3u8",
            video="copy",
            audio="transcode",
            subtitles="burn" if burn else ("text" if options.subtitle else "none"),
        )

    @asynccontextmanager
    async def open(self, session: str, path: str) -> AsyncIterator[StreamBody]:
        if not path.startswith(f"session/{session}/base/"):
            raise ProviderNotFound("no such part")
        self.owner.calls.append((self.account, "open", path))
        data = b"#EXTM3U\n#EXTINF:10,\n00000.ts\n" if path.endswith(".m3u8") else b"\x47" * 1880

        async def chunks() -> AsyncIterator[bytes]:
            yield data[: len(data) // 2]
            yield data[len(data) // 2 :]

        kind = "application/vnd.apple.mpegurl" if path.endswith(".m3u8") else "video/mp2t"
        yield StreamBody(status=200, content_type=kind, length=len(data), chunks=chunks())

    @asynccontextmanager
    async def subtitles(
        self, external_id: str, options: StreamOptions, session: str
    ) -> AsyncIterator[AsyncIterator[SubtitleCue]]:
        self.owner.calls.append((self.account, "subtitles", options.subtitle))

        async def cues() -> AsyncIterator[SubtitleCue]:
            for cue in self.owner.cues:
                yield cue
            await asyncio.sleep(3600)  # the feed stays open, as the service's does

        yield cues()

    async def report(
        self, external_id: str, session: str, state: str, position_s: float, duration_s: float | None
    ) -> None:
        self.owner.calls.append((self.account, "report", (state, position_s, duration_s)))

    async def stop(self, session: str) -> None:
        self.owner.calls.append((self.account, "stop", session))

    async def continuing(self, limit: int) -> list[ResumePoint]:
        if self.account == "denied":
            raise ProviderAuthError("no access")
        self.owner.calls.append((self.account, "continuing", limit))
        return list(self.owner.resume)[:limit]

    async def reset(self, external_id: str) -> None:
        self._check(external_id)
        self.owner.calls.append((self.account, "reset", external_id))

    async def image(self, ref: str, at_s: float | None = None) -> bytes:
        if ref != "chapter:1:2":
            raise ProviderNotFound("no such picture")
        self.owner.calls.append((self.account, "image", ref))
        return PNG_1PX
