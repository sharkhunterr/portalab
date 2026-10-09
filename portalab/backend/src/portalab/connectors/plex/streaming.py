"""``media.streaming`` for Plex (027, #2): the portal's own player, fed by Plex's universal transcoder.

* **As the member's account.** A member linked to a Plex account plays *as that account*: the server owner's
  token reads, on plex.tv, the access token Plex issued to each user the server is shared with
  (``/api/servers/<machine>/shared_servers``, what Plex's own tools do). So the member's library rights,
  resume points, « watched » marks, audio and subtitle choices and Tautulli history stay theirs. The tokens
  live in this process only (refreshed every half hour) and never reach a browser.
* **Plex decides.** ``/video/:/transcode/universal/decision`` then ``start.m3u8`` (HLS): Plex streams the
  video as it is when the browser can play it (only the audio converted, typically), and transcodes
  otherwise — or when the member picks a lower quality, or a subtitle to burn in.
* **Subtitles.** Text subtitles are read from the transcoder's subtitle feed (``…/subtitles``, ASS) and
  drawn by the player; image formats (PGS, VobSub) are burnt into the picture, as Plex Web does.
* **Activity.** ``/:/timeline`` reports where the member is: resume point, « watched », and the session the
  activity poller and Tautulli see.
"""

import codecs
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import (
    QUALITIES,
    PlayableItem,
    ResumePoint,
    StreamBody,
    StreamMarker,
    StreamOptions,
    StreamStart,
    StreamTrack,
    StreamVersion,
    SubtitleCue,
    resolution_of,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.connectors.http_base import HttpConnector, parse_time, safe_id
from portalab.core.logging import register_secret_value

PLEX_TV = "https://plex.tv"
TOKEN_TTL = 1800.0
OWNER = "1"  # the server owner's account id on the server (``/accounts``)
TRANSCODER = "/video/:/transcode/universal"
SEGMENT = re.compile(r"^session/([A-Za-z0-9_-]{1,80})/base/(index\.m3u8|\d{1,6}\.ts)$")
CHAPTER_IMAGE = re.compile(r"^/library/media/(\d{1,12})/chapterImages/(\d{1,4})$")
IMAGE_REF = re.compile(r"^(chapter|preview):(\d{1,12})(?::(\d{1,4}))?$")
IMAGE_SUBTITLES = frozenset({"pgs", "hdmv_pgs_subtitle", "vobsub", "dvd_subtitle", "dvdsub", "dvb_subtitle"})
RESOLUTION_LABELS = {"4k": "4K", "1080p": "1080p", "720p": "720p", "sd": "SD"}
CODEC_LABELS = {
    "h264": "H.264",
    "hevc": "HEVC",
    "h265": "HEVC",
    "av1": "AV1",
    "mpeg4": "MPEG-4",
    "vc1": "VC-1",
}
_TOKENS: dict[str, tuple[float, dict[str, str]]] = {}  # service id → (fetched at, {account id: token})
_MACHINES: dict[str, str] = {}


def _container(document: Any) -> Mapping[str, Any]:
    if not isinstance(document, Mapping) or not isinstance(document.get("MediaContainer"), Mapping):
        raise InvalidPayload("not a Plex MediaContainer")
    container: Mapping[str, Any] = document["MediaContainer"]
    return container


def _first(container: Mapping[str, Any]) -> Mapping[str, Any]:
    items = container.get("Metadata") or []
    if not items or not isinstance(items[0], Mapping):
        raise ProviderNotFound("the server has no such item")
    item: Mapping[str, Any] = items[0]
    return item


def _seconds(ms: Any) -> float | None:
    return round(ms / 1000, 3) if isinstance(ms, int | float) and ms > 0 else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _track(stream: Mapping[str, Any]) -> StreamTrack:
    kind = "audio" if stream.get("streamType") == 2 else "subtitle"
    codec = str(stream.get("codec") or "").lower() or None
    label = stream.get("extendedDisplayTitle") or stream.get("displayTitle") or stream.get("language") or "?"
    return StreamTrack(
        id=str(stream.get("id")),
        kind=kind,
        label=str(label)[:200],
        language=stream.get("languageCode") or stream.get("language"),
        codec=codec,
        channels=_int(stream.get("channels")),
        default=bool(stream.get("default")),
        forced=bool(stream.get("forced")),
        selected=bool(stream.get("selected")),
        text=codec not in IMAGE_SUBTITLES,
        external=bool(stream.get("key")),
    )


def _version(index: int, media: Mapping[str, Any]) -> StreamVersion:
    parts = media.get("Part") or [{}]
    streams = parts[0].get("Stream") or []
    video: Mapping[str, Any] = next((s for s in streams if s.get("streamType") == 1), {})
    resolution = resolution_of(media.get("videoResolution"))
    raw_codec = str(media.get("videoCodec") or "").lower()
    codec = CODEC_LABELS.get(raw_codec, raw_codec.upper())
    hdr = "hdr" in str(video.get("displayTitle") or "").lower() or bool(video.get("DOVIPresent"))
    label = " · ".join(
        bit
        for bit in (
            RESOLUTION_LABELS.get(resolution or "", ""),
            codec,
            "HDR" if hdr else "",
            str(media.get("container") or ""),
        )
        if bit
    )
    return StreamVersion(
        index=index,
        label=label or f"#{index + 1}",
        resolution=resolution,
        width=_int(media.get("width")),
        height=_int(media.get("height")),
        bitrate_kbps=_int(media.get("bitrate")),
        container=media.get("container"),
        video_codec=media.get("videoCodec"),
        audio_codec=media.get("audioCodec"),
        hdr=hdr,
        size=_int(parts[0].get("size")),
        audio=tuple(_track(s) for s in streams if s.get("streamType") == 2),
        subtitles=tuple(_track(s) for s in streams if s.get("streamType") == 3),
        # the server's preview thumbnails, when it generates them (Plex: « video preview thumbnails »)
        previews=f"preview:{parts[0]['id']}" if parts[0].get("indexes") and parts[0].get("id") else None,
    )


def _markers(item: Mapping[str, Any]) -> tuple[StreamMarker, ...]:
    out = []
    for marker in item.get("Marker") or []:
        kind = marker.get("type")
        start, end = _seconds(marker.get("startTimeOffset")) or 0.0, _seconds(marker.get("endTimeOffset"))
        if kind in ("intro", "credits") and end and end > start:
            out.append(StreamMarker(kind=str(kind), start_s=start, end_s=end))
    return tuple(out)


def _chapters(item: Mapping[str, Any]) -> tuple[StreamMarker, ...]:
    out = []
    for chapter in item.get("Chapter") or []:
        start, end = _seconds(chapter.get("startTimeOffset")) or 0.0, _seconds(chapter.get("endTimeOffset"))
        if end and end > start:
            thumb = CHAPTER_IMAGE.match(str(chapter.get("thumb") or ""))
            out.append(
                StreamMarker(
                    kind="chapter",
                    start_s=start,
                    end_s=end,
                    label=chapter.get("tag") or None,
                    image=f"chapter:{thumb.group(1)}:{thumb.group(2)}" if thumb else None,
                )
            )
    return tuple(out)


def _guids(item: Mapping[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for guid in item.get("Guid") or []:
        scheme, _, value = str(guid.get("id", "")).partition("://")
        if scheme in ("tmdb", "imdb", "tvdb") and value:
            ids[scheme] = value
    return ids


def _episode_label(item: Mapping[str, Any]) -> str | None:
    season, episode = _int(item.get("parentIndex")), _int(item.get("index"))
    if season is None or episode is None:
        return None
    return f"S{season:02d}E{episode:02d}"


def _clock(text: str) -> float | None:
    """« 0:02:12.22 » (ASS) or « 00:02:12.220 » (WebVTT) → seconds."""
    match = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})", text.strip())
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    whole = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    return whole + int(fraction) / float(10 ** len(fraction))


_ASS_TAGS = re.compile(r"\{[^}]*\}")


def _ass_text(raw: str) -> str:
    text = _ASS_TAGS.sub("", raw).replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
    return "\n".join(line.strip() for line in text.replace("\r", "").split("\n") if line.strip())


async def _cues(chunks: AsyncIterator[bytes]) -> AsyncIterator[SubtitleCue]:
    """The transcoder's subtitle feed (ASS ``Dialogue`` lines — or WebVTT blocks) as cues, as they come."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buffer = ""
    pending: tuple[float, float] | None = None  # a WebVTT timing line waiting for its text
    lines: list[str] = []
    async for chunk in chunks:
        buffer += decoder.decode(chunk)
        *complete, buffer = buffer.split("\n")
        for raw in complete:
            line = raw.rstrip("\r")
            if line.startswith("Dialogue:"):
                fields = line[len("Dialogue:") :].split(",", 9)
                if len(fields) == 10:
                    start, end, text = _clock(fields[1]), _clock(fields[2]), _ass_text(fields[9])
                    if start is not None and end is not None and text:
                        yield SubtitleCue(start_s=start, end_s=end, text=text[:500])
                continue
            if "-->" in line:
                left, _, right = line.partition("-->")
                start, end = _clock(left), _clock(right.strip().split(" ")[0])
                pending, lines = ((start, end) if start is not None and end is not None else None), []
                continue
            if pending is not None:
                if line.strip():
                    lines.append(line.strip())
                    continue
                if lines:
                    yield SubtitleCue(start_s=pending[0], end_s=pending[1], text="\n".join(lines)[:500])
                pending, lines = None, []


class PlexStreaming:
    def __init__(self, connector: HttpConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    def channel(self, external_user_id: str | None) -> "PlexChannel":
        return PlexChannel(self.connector, self.service, external_user_id)


class PlexChannel:
    def __init__(self, connector: HttpConnector, service: ServiceHandle, account: str | None) -> None:
        self.connector, self.service = connector, service
        self.account = account or OWNER
        # one stable « device » per account on the server (its Devices list stays short)
        digest = hashlib.sha256(f"{service.service_id}:{self.account}".encode()).hexdigest()[:16]
        self.client_id = f"portalab-{digest}"

    # --- tokens ------------------------------------------------------------------------------------------
    async def _machine(self) -> str:
        key = str(self.service.service_id)
        if key not in _MACHINES:
            identity = _container(await self.connector.get_json(self.service, "/identity"))
            machine = str(identity.get("machineIdentifier") or "")
            if not machine:
                raise InvalidPayload("the server did not tell its identifier")
            _MACHINES[key] = machine
        return _MACHINES[key]

    async def _token(self) -> str:
        owner = self.service.secrets.get("token", "")
        if self.account == OWNER:
            return owner
        key = str(self.service.service_id)
        fetched, tokens = _TOKENS.get(key, (0.0, {}))
        if time.monotonic() - fetched > TOKEN_TTL or self.account not in tokens:
            tokens = await self._shared_tokens(owner)
            _TOKENS[key] = (time.monotonic(), tokens)
        token = tokens.get(self.account)
        if not token:
            raise ProviderAuthError("this Plex account has no access to the server")
        return token

    async def _shared_tokens(self, owner: str) -> dict[str, str]:
        machine = await self._machine()
        client = ConnectorHttpClient(
            PLEX_TV,
            timeout_seconds=10,
            retries=1,
            secrets={"token": owner},
            transport=getattr(self.service.http, "transport", None),  # a test's fake network
        )
        try:
            response = await client.get(
                f"/api/servers/{safe_id(machine)}/shared_servers",
                headers={"X-Plex-Token": owner, "X-Plex-Client-Identifier": self.client_id},
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("plex.tv rejected the server owner's token")
        if response.status_code >= 400:
            raise ConnectionError(f"plex.tv answered HTTP {response.status_code}")
        try:
            root = ET.fromstring(response.content)  # noqa: S314 — see the import
        except ET.ParseError as exc:
            raise InvalidPayload("plex.tv did not answer with XML") from exc
        tokens: dict[str, str] = {}
        for shared in root:
            user, token = shared.attrib.get("userID"), shared.attrib.get("accessToken")
            if user and token:
                register_secret_value(token)
                tokens[user] = token
        return tokens

    # --- HTTP ----------------------------------------------------------------------------------------------
    def _headers(self, token: str, session: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Plex-Token": token,
            "X-Plex-Client-Identifier": self.client_id,
            "X-Plex-Product": "Portalab",
            "X-Plex-Version": "1.0",
            "X-Plex-Platform": "Chrome",
            "X-Plex-Device": "Portalab",
            "X-Plex-Device-Name": "Portalab",
        }
        if session:
            headers["X-Plex-Session-Identifier"] = session
        return headers

    async def _call(
        self, method: str, path: str, params: Mapping[str, Any] | None = None, *, session: str | None = None
    ) -> Any:
        token = await self._token()
        return await self.connector.request(
            self.service, method, path, params=params, headers=self._headers(token, session)
        )

    async def _text(self, path: str, params: Mapping[str, Any], session: str) -> str:
        token = await self._token()
        try:
            response = await self.connector._http(self.service).get(
                path, headers=self._headers(token, session), params=dict(params)
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the server refused this account")
        if response.status_code >= 400:
            raise ConnectionError(f"the server answered HTTP {response.status_code}")
        return response.content.decode("utf-8", errors="replace")

    async def _metadata(self, key: str, **extra: Any) -> Mapping[str, Any]:
        return _first(_container(await self._call("GET", f"/library/metadata/{safe_id(key)}", extra or None)))

    async def _leaves(self, key: str, path: str = "allLeaves") -> list[Mapping[str, Any]]:
        container = _container(await self._call("GET", f"/library/metadata/{safe_id(key)}/{path}"))
        return [m for m in container.get("Metadata") or [] if isinstance(m, Mapping)]

    # --- the title -----------------------------------------------------------------------------------------
    async def _episode_of(self, item: Mapping[str, Any]) -> Mapping[str, Any]:
        """A series or a season plays its next episode: Plex's « on deck » for the account, or the first
        one not seen yet, or the first."""
        key = str(item.get("ratingKey"))
        if item.get("type") == "show":
            deck = (item.get("OnDeck") or {}).get("Metadata")
            deck = deck[0] if isinstance(deck, list) and deck else deck
            if isinstance(deck, Mapping) and deck.get("ratingKey"):
                return deck
            episodes = await self._leaves(key)
        else:
            episodes = await self._leaves(key, "children")
        if not episodes:
            raise ProviderNotFound("nothing to play in this series")
        return next((e for e in episodes if not e.get("viewCount")), episodes[0])

    async def _neighbours(self, item: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
        show = item.get("grandparentRatingKey")
        if item.get("type") != "episode" or not show:
            return None, None, None
        episodes = sorted(
            await self._leaves(str(show)),
            key=lambda e: (_int(e.get("parentIndex")) or 0, _int(e.get("index")) or 0),
        )
        keys = [str(e.get("ratingKey")) for e in episodes]
        here = str(item.get("ratingKey"))
        if here not in keys:
            return None, None, None
        at = keys.index(here)
        previous = keys[at - 1] if at > 0 else None
        following = episodes[at + 1] if at + 1 < len(episodes) else None
        return (
            previous,
            str(following.get("ratingKey")) if following else None,
            _episode_label(following) if following else None,
        )

    async def playable(self, external_id: str) -> PlayableItem:
        item = await self._metadata(external_id, includeOnDeck=1)
        if item.get("type") in ("show", "season"):
            item = await self._episode_of(item)
        kind = item.get("type")
        if kind not in ("movie", "episode"):
            raise ProviderNotFound("this item cannot be played here")
        key = str(item.get("ratingKey"))
        item = await self._metadata(key, includeMarkers=1, includeChapters=1)
        versions = tuple(
            _version(i, m) for i, m in enumerate(item.get("Media") or []) if isinstance(m, Mapping)
        )
        if not versions:
            raise ProviderNotFound("this item has no file")
        previous, following, following_label = await self._neighbours(item)
        return PlayableItem(
            external_id=key,
            kind=str(kind),
            title=str(item.get("title") or "?")[:500],
            duration_s=_seconds(item.get("duration")),
            resume_s=_seconds(item.get("viewOffset")) or 0.0,
            watched=bool(item.get("viewCount")),
            parent_title=item.get("grandparentTitle") if kind == "episode" else None,
            label=_episode_label(item) if kind == "episode" else None,
            year=_int(item.get("year")),
            versions=versions,
            markers=_markers(item),
            chapters=_chapters(item),
            previous_id=previous,
            next_id=following,
            next_label=following_label,
            image=key if item.get("thumb") else None,
        )

    # --- the stream ----------------------------------------------------------------------------------------
    def _params(
        self, external_id: str, options: StreamOptions, session: str, *, burn: bool
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "path": f"/library/metadata/{safe_id(external_id)}",
            "mediaIndex": max(options.version, 0),
            "partIndex": 0,
            "protocol": "hls",
            "fastSeek": 1,
            "copyts": 1,
            "directPlay": 0,
            "directStream": 1,
            "directStreamAudio": 1,
            "location": "lan",
            "session": session,
            "subtitles": "burn" if burn else "auto",
            "subtitleSize": min(max(options.subtitle_size, 50), 300),
            "audioBoost": min(max(options.boost, 100), 300),
            "mediaBufferSize": 102400,
            "X-Plex-Session-Identifier": session,
        }
        cap = QUALITIES.get(options.quality)
        if cap is None:
            params.update(videoQuality=100, maxVideoBitrate=200_000, videoResolution="3840x2160")
        else:
            kbps, width, height = cap
            params.update(videoQuality=100, maxVideoBitrate=kbps, videoResolution=f"{width}x{height}")
        return params

    async def _select(self, item: Mapping[str, Any], options: StreamOptions) -> StreamTrack | None:
        """The member's audio and subtitle choice, stored on their account as Plex's apps do."""
        media = (item.get("Media") or [])[max(options.version, 0) :] or (item.get("Media") or [])
        if not media:
            raise ProviderNotFound("this item has no file")
        part = (media[0].get("Part") or [{}])[0]
        tracks = [_track(s) for s in part.get("Stream") or [] if s.get("streamType") in (2, 3)]
        subtitle = next((t for t in tracks if t.kind == "subtitle" and t.id == options.subtitle), None)
        audio = next((t for t in tracks if t.kind == "audio" and t.id == options.audio), None)
        params: dict[str, Any] = {"allParts": 1, "subtitleStreamID": subtitle.id if subtitle else 0}
        if audio is not None:
            params["audioStreamID"] = audio.id
        if part.get("id"):
            await self._call("PUT", f"/library/parts/{safe_id(part['id'])}", params)
        return subtitle

    async def start(self, external_id: str, options: StreamOptions, session: str) -> StreamStart:
        item = await self._metadata(external_id)
        subtitle = await self._select(item, options)
        burn = subtitle is not None and (options.burn or not subtitle.text)
        params = self._params(external_id, options, session, burn=burn)
        decision = _container(await self._call("GET", f"{TRANSCODER}/decision", params, session=session))
        chosen = (decision.get("Metadata") or [{}])[0]
        media = (chosen.get("Media") or [None])[0]
        if not isinstance(media, Mapping):
            raise ConnectionError(str(decision.get("generalDecisionText") or "the server cannot play this"))
        streams = (media.get("Part") or [{}])[0].get("Stream") or []
        video: Mapping[str, Any] = next((s for s in streams if s.get("streamType") == 1), {})
        audio: Mapping[str, Any] = next((s for s in streams if s.get("streamType") == 2), {})
        master = await self._text(f"{TRANSCODER}/start.m3u8", params, session)
        playlist = next(
            (ln.strip() for ln in master.splitlines() if ln.strip() and not ln.startswith("#")), ""
        )
        match = SEGMENT.match(playlist)
        if not match or match.group(1) != session:
            raise InvalidPayload("unexpected playlist from the transcoder")
        return StreamStart(
            session=session,
            playlist=playlist,
            video="copy" if video.get("decision") == "copy" else "transcode",
            audio="copy" if audio.get("decision") == "copy" else "transcode",
            subtitles="burn" if burn else ("text" if subtitle is not None else "none"),
            width=_int(media.get("width")),
            height=_int(media.get("height")),
            bitrate_kbps=_int(media.get("bitrate")),
            video_codec=media.get("videoCodec"),
            audio_codec=media.get("audioCodec"),
        )

    @asynccontextmanager
    async def open(self, session: str, path: str) -> AsyncIterator[StreamBody]:
        match = SEGMENT.match(path)
        if not match or match.group(1) != session:
            raise ProviderNotFound("no such part of the stream")
        token = await self._token()
        # relayed as they are: no compression, so the length the server announces is the one sent on
        headers = {**self._headers(token, session), "Accept-Encoding": "identity"}
        async with self.connector._http(self.service).stream(
            "GET", f"{TRANSCODER}/{path}", headers=headers, read_timeout=90
        ) as response:
            if response.status_code in (401, 403):
                raise ProviderAuthError("the server refused this account")
            if response.status_code in (404, 410):
                raise ProviderNotFound("the stream ended")
            if response.status_code >= 400:
                raise ConnectionError(f"the server answered HTTP {response.status_code}")
            encoded = response.headers.get("content-encoding", "identity") != "identity"
            length = None if encoded else response.headers.get("content-length")
            yield StreamBody(
                status=response.status_code,
                content_type=response.headers.get("content-type")
                or ("application/vnd.apple.mpegurl" if path.endswith(".m3u8") else "video/mp2t"),
                length=int(length) if length and length.isdigit() else None,
                chunks=response.chunks,
            )

    @asynccontextmanager
    async def subtitles(
        self, external_id: str, options: StreamOptions, session: str
    ) -> AsyncIterator[AsyncIterator[SubtitleCue]]:
        token = await self._token()
        params = self._params(external_id, options, session, burn=False)
        async with self.connector._http(self.service).stream(
            "GET",
            f"{TRANSCODER}/subtitles",
            headers=self._headers(token, session),
            params=params,
            read_timeout=600,
        ) as response:
            if response.status_code >= 400:
                raise ConnectionError(f"the server answered HTTP {response.status_code}")
            yield _cues(response.chunks)

    async def report(
        self, external_id: str, session: str, state: str, position_s: float, duration_s: float | None
    ) -> None:
        key = safe_id(external_id)
        params: dict[str, Any] = {
            "ratingKey": key,
            "key": f"/library/metadata/{key}",
            "state": state if state in ("playing", "paused", "stopped", "buffering") else "playing",
            "time": int(max(position_s, 0) * 1000),
            "hasMDE": 1,
        }
        if duration_s:
            params["duration"] = int(duration_s * 1000)
        await self._call("GET", "/:/timeline", params, session=session)
        if state == "paused":  # the transcoder stops a session it has not heard from for a while
            await self._call("GET", f"{TRANSCODER}/ping", {"session": session}, session=session)

    async def image(self, ref: str, at_s: float | None = None) -> bytes:
        match = IMAGE_REF.match(ref)
        if not match or (match.group(1) == "chapter") != (match.group(3) is not None):
            raise ProviderNotFound("no such picture")
        kind, key, number = match.groups()
        params: dict[str, Any] = {}
        if kind == "chapter":  # scaled down by the server's photo transcoder (the original is full size)
            path = "/photo/:/transcode"
            params = {"url": f"/library/media/{key}/chapterImages/{number}", "width": 320, "height": 180}
        else:
            path = f"/library/parts/{key}/indexes/sd/{int(max(at_s or 0.0, 0.0) * 1000)}"
        token = await self._token()
        try:
            response = await self.connector._http(self.service).get(
                path, headers=self._headers(token), params=params
            )
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code in (401, 403):
            raise ProviderAuthError("the server refused this account")
        if response.status_code >= 400 or not response.content:
            raise ProviderNotFound("no such picture")
        return response.content

    async def reset(self, external_id: str) -> None:
        """Plex keeps a resume point against any smaller progress: ``unscrobble`` clears it (and
        « watched »), so a title seen before is marked seen again — seen, with nothing to resume."""
        key = safe_id(external_id)
        item = await self._metadata(key)
        target = {"key": key, "identifier": "com.plexapp.plugins.library"}
        await self._call("GET", "/:/unscrobble", target)
        if item.get("viewCount"):
            await self._call("GET", "/:/scrobble", target)

    async def continuing(self, limit: int) -> list[ResumePoint]:
        """Plex's own « Continue watching » hub for the account: titles started (with their position)
        and the next episode of the series being followed (no position)."""
        container = _container(
            await self._call(
                "GET", "/hubs/continueWatching", {"count": max(1, min(limit, 50)), "includeGuids": 1}
            )
        )
        items = list(container.get("Metadata") or [])
        for hub in container.get("Hub") or []:
            items.extend(hub.get("Metadata") or [])
        out: list[ResumePoint] = []
        for item in items:
            kind = item.get("type")
            if kind not in ("movie", "episode") or not item.get("ratingKey"):
                continue
            out.append(
                ResumePoint(
                    external_id=str(item["ratingKey"]),
                    kind=str(kind),
                    title=str(item.get("title") or "?")[:500],
                    parent_title=item.get("grandparentTitle") if kind == "episode" else None,
                    label=_episode_label(item) if kind == "episode" else None,
                    position_s=_seconds(item.get("viewOffset")) or 0.0,
                    duration_s=_seconds(item.get("duration")),
                    at=parse_time(item.get("lastViewedAt")),
                    ids=_guids(item),
                    year=_int(item.get("year")),
                )
            )
        return out[:limit]

    async def stop(self, session: str) -> None:
        await self._call("GET", f"{TRANSCODER}/stop", {"session": session}, session=session)
