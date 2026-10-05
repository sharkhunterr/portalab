"""``grimmory`` connector: Grimmory (BookLore fork), the books and audiobooks library (API v1).

* ``media.library`` (sync): every book — e-books (EPUB, PDF, comics, MOBI…) as ``book``, audiobooks as
  ``audiobook`` — with authors, categories, series, publisher, ISBN, page count and cover.
* ``media.activity_history``: the reading and listening sessions (start, end, time spent, progress).
  Grimmory only reveals the sessions of the signed-in account, so they belong to the account configured
  here; connect one service per reader to follow several.
* ``service.accounts``: Grimmory users (administrator account needed; otherwise the configured one).
* ``service.health_probe``: an authenticated round trip.

Authentication: a Grimmory username (configuration) and password (secret) exchanged for a short-lived
bearer token (``POST /api/v1/auth/login``), renewed before it expires or when refused.
"""

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import (
    ACCOUNTS,
    ACTIVITY_HISTORY,
    LIBRARY,
    ActivityPage,
    ServiceAccount,
    SourceActivity,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError
from portalab.connectors.http_base import (
    LIBRARY_LISTING_BYTES,
    BaseConfig,
    HttpConnector,
    _Probe,
    binding,
    parse_time,
    safe_id,
)

AUDIOBOOK = "AUDIOBOOK"
BOOKS_PER_PAGE = 20  # books whose sessions are read per activity page
SESSION_PAGE = 100
MARGIN_S = 30


class GrimmoryConfig(BaseConfig):
    username: str = Field(min_length=1, max_length=128, title="Username")


def _content(body: Any) -> list[Mapping[str, Any]]:
    if isinstance(body, list):
        return [b for b in body if isinstance(b, Mapping)]
    if isinstance(body, Mapping) and isinstance(body.get("content"), list):
        return [b for b in body["content"] if isinstance(b, Mapping)]
    return []


def _meta(book: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = book.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


def book_type(book: Mapping[str, Any]) -> str:
    primary = book.get("primaryFile") or {}
    return str(
        (primary.get("bookType") if isinstance(primary, Mapping) else None) or book.get("bookType") or ""
    )


def kind_of(book: Mapping[str, Any]) -> str:
    return "audiobook" if book_type(book).upper() == AUDIOBOOK else "book"


def _names(values: Any) -> list[str]:
    out = []
    for value in values or []:
        name = value.get("name") if isinstance(value, Mapping) else value
        if isinstance(name, str) and name.strip():
            out.append(name.strip()[:200])
    return out


def map_book(book: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]] | None:
    """A Grimmory book as ``(external id, kind, LibraryPayload)``; ``None`` without id or title."""
    meta = _meta(book)
    title = meta.get("title") or book.get("title")
    if book.get("id") is None or not title:
        return None
    published = parse_time(meta.get("publishedDate"))
    ids = {
        scheme: str(meta[field])[:200]
        for scheme, field in (("isbn", "isbn13"), ("isbn10", "isbn10"))
        if meta.get(field)
    }
    if "isbn" not in ids and "isbn10" in ids:
        ids["isbn"] = ids["isbn10"]
    ids.pop("isbn10", None)
    if meta.get("openLibraryId"):
        ids["openlibrary"] = str(meta["openLibraryId"])[:200]
    people = _names(meta.get("authors"))
    if meta.get("narrator"):
        people += _names([meta["narrator"]])
    subtitle = meta.get("subtitle")
    payload = {
        "title": str(title)[:500],
        "original_title": f"{title} — {subtitle}"[:500] if subtitle else None,
        "ids": ids,
        "year": published.year if published else None,
        "overview": (str(meta.get("description") or "")[:5000]) or None,
        "genres": _names(meta.get("categories"))[:30],
        "people": people[:50],
        "language": (str(meta.get("language"))[:16] if meta.get("language") else None),
        "pages": int(meta["pageCount"]) if str(meta.get("pageCount") or "").isdigit() else None,
        "duration_s": float(meta["audiobookDuration"]) if meta.get("audiobookDuration") else None,
        # an audiobook's cover is served apart (027): ``a-<id>`` names it
        "image": f"a-{book['id']}" if kind_of(book) == "audiobook" else str(book["id"]),
        "series": (str(meta.get("seriesName"))[:200] if meta.get("seriesName") else None),
        "series_position": meta.get("seriesNumber"),
        "publisher": (str(meta.get("publisher"))[:200] if meta.get("publisher") else None),
    }
    return safe_id(book["id"]), kind_of(book), payload


def map_session(session: Mapping[str, Any], book: Mapping[str, Any], user: str) -> SourceActivity | None:
    started = parse_time(session.get("startTime"))
    if started is None or session.get("id") is None:
        return None
    ended = parse_time(session.get("endTime"))
    duration = session.get("durationSeconds")
    if duration is None and ended is not None:
        duration = (ended - started).total_seconds()
    end_progress = session.get("endProgress")
    progress = float(end_progress) if isinstance(end_progress, int | float) else None
    if progress is not None and progress > 1:
        progress = progress / 100  # Grimmory reports percentages
    mapped = map_book(book)
    if str(session.get("bookType") or "").upper() == AUDIOBOOK:
        kind = "audiobook"
    else:
        kind = mapped[1] if mapped else "book"
    meta = _meta(book)
    authors = _names(meta.get("authors"))
    return SourceActivity(
        ref=str(session["id"]),
        external_user_id=user,
        kind=kind,
        title=str(meta.get("title") or session.get("bookTitle") or book.get("title") or "?")[:500],
        started_at=started,
        stopped_at=ended,
        watched_s=max(0.0, float(duration or 0)),
        progress=min(1.0, max(0.0, progress)) if progress is not None else None,
        item_external_id=str(book.get("id")),
        parent_title=authors[0] if authors else None,
        ids=mapped[2]["ids"] if mapped else {},
        year=mapped[2].get("year") if mapped else None,
        family=None,
        priority=10,
    )


class GrimmoryConnector(HttpConnector):
    key = "grimmory"
    name = "Grimmory"
    description = "Your books and audiobooks library, and the reading and listening sessions."
    icon = "book"
    category = "books"
    config_schema: type[BaseModel] = GrimmoryConfig
    secret_fields: frozenset[str] = frozenset({"password"})
    provides: Sequence[CapabilityBinding] = (
        binding(LIBRARY, syncable=True),
        binding(ACTIVITY_HISTORY),
        binding(ACCOUNTS),
        binding(HEALTH_PROBE),
    )
    status_path = "/api/v1/libraries"
    public_path = "/api/v1/healthcheck"

    def __init__(self) -> None:
        self._tokens: dict[UUID, tuple[str, float]] = {}
        self._self_ids: dict[UUID, str] = {}

    # --- authentication -------------------------------------------------------------------------------
    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        token = self._tokens.get(service.service_id)
        return {"Authorization": f"Bearer {token[0]}"} if token else {}

    async def _login(self, service: ServiceHandle) -> None:
        self._tokens.pop(service.service_id, None)
        body = await super().request(
            service,
            "POST",
            "/api/v1/auth/login",
            json_body={
                "username": service.config.get("username", ""),
                "password": service.secrets.get("password", ""),
            },
        )
        token = body.get("accessToken") if isinstance(body, Mapping) else None
        if not token:
            raise ProviderAuthError("Grimmory refused the credentials")
        try:
            expires = float(body.get("expires") or 3600)
        except (TypeError, ValueError):
            expires = 3600.0
        now = time.time()
        if expires > 10**10:  # milliseconds since the epoch
            expires_at = expires / 1000
        elif expires > 10**9:  # seconds since the epoch
            expires_at = expires
        else:  # a lifetime in seconds
            expires_at = now + max(60.0, expires)
        self._tokens[service.service_id] = (str(token), expires_at)

    async def _ensure(self, service: ServiceHandle) -> None:
        token = self._tokens.get(service.service_id)
        if token is None or time.time() > token[1] - MARGIN_S:
            await self._login(service)

    async def request(
        self,
        service: ServiceHandle,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> Any:
        await self._ensure(service)
        call = {"params": params, "json_body": json_body, "headers": headers, "max_bytes": max_bytes}
        try:
            return await super().request(service, method, path, **call)
        except ProviderAuthError:
            await self._login(service)  # the token may have been revoked: one fresh attempt
            return await super().request(service, method, path, **call)

    async def get_bytes(self, service: ServiceHandle, path: str, **params: Any) -> bytes:
        await self._ensure(service)
        try:
            return await super().get_bytes(service, path, **params)
        except ProviderAuthError:
            await self._login(service)
            return await super().get_bytes(service, path, **params)

    def describe(self, status: Any) -> str:
        if not isinstance(status, list):
            raise InvalidPayload("not a Grimmory library list")
        return f"Grimmory ({len(status)} libraries)"

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and ("status" in public or "version" in public)

    # --- library --------------------------------------------------------------------------------------
    async def books(self, service: ServiceHandle) -> list[Mapping[str, Any]]:
        return _content(
            await self.request(
                service,
                "GET",
                "/api/v1/books",
                params={"stripForListView": "false"},
                max_bytes=LIBRARY_LISTING_BYTES,
            )
        )

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        count = 0
        books = await self.books(ctx.service)
        yield SyncProgress(cursor={}, total=len(books))
        for book in books:
            mapped = map_book(book)
            if mapped is None:
                continue
            external_id, kind, payload = mapped
            observed = parse_time(book.get("addedOn") or book.get("addedAt"))
            yield self.record(ctx.service, external_id, kind, payload, observed)
            count += 1
        yield SyncProgress(cursor={"items": count})

    async def self_id(self, service: ServiceHandle) -> str:
        """The Grimmory id of the configured account (its sessions are the ones Grimmory reveals)."""
        known = self._self_ids.get(service.service_id)
        if known:
            return known
        username = str(service.config.get("username", ""))
        found = f"user:{username}"
        try:
            for user in _content(await self.get_json(service, "/api/v1/users")):
                if str(user.get("username", "")).lower() == username.lower() and user.get("id") is not None:
                    found = str(user["id"])
                    break
        except (ProviderAuthError, InvalidPayload, ConnectionError):
            pass  # not an administrator: the account is named by its username
        self._self_ids[service.service_id] = found
        return found

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == LIBRARY:
            return _Covers(self, service)
        if capability == ACTIVITY_HISTORY:
            return _Sessions(self, service)
        if capability == ACCOUNTS:
            return _Accounts(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Covers:
    def __init__(self, connector: GrimmoryConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        if ref.startswith("a-"):  # an audiobook (027): its own cover endpoint
            return await self.connector.get_bytes(
                self.service, f"/api/v1/media/book/{safe_id(ref[2:])}/audiobook-cover"
            )
        return await self.connector.get_bytes(self.service, f"/api/v1/media/book/{safe_id(ref)}/cover")


class _Sessions:
    """Sessions are listed per book: the backfill walks every book (a page of books per call); then only
    the books read since the last run when Grimmory tells when a book was last read."""

    def __init__(self, connector: GrimmoryConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def _sessions(self, book_id: str) -> list[Mapping[str, Any]]:
        out: list[Mapping[str, Any]] = []
        for page in range(50):
            rows = _content(
                await self.connector.get_json(
                    self.service,
                    f"/api/v1/reading-sessions/book/{book_id}",
                    page=page,
                    size=SESSION_PAGE,
                )
            )
            out.extend(rows)
            if len(rows) < SESSION_PAGE:
                break
        return out

    async def history(self, *, since: datetime | None, cursor: str | None) -> ActivityPage:
        books = sorted(await self.connector.books(self.service), key=lambda b: str(b.get("id")))
        if since is not None:
            read = [b for b in books if parse_time(b.get("lastReadTime")) is not None]
            if read:  # Grimmory tells when each book was last read: only those since the last run
                books = [b for b in read if (parse_time(b.get("lastReadTime")) or since) >= since]
        start = int(cursor) if cursor and cursor.isdigit() else 0
        user = await self.connector.self_id(self.service)
        items: list[SourceActivity] = []
        for book in books[start : start + BOOKS_PER_PAGE]:
            if book.get("id") is None:
                continue
            for session in await self._sessions(safe_id(book["id"])):
                activity = map_session(session, book, user)
                if activity is not None and (since is None or activity.started_at >= since):
                    items.append(activity)
        end = start + BOOKS_PER_PAGE
        return ActivityPage(
            items=items,
            cursor=str(end) if end < len(books) else None,
            total=len(books),  # progress counts books: sessions are read book by book
            position=min(end, len(books)),
        )


class _Accounts:
    def __init__(self, connector: GrimmoryConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def list_accounts(self) -> Sequence[ServiceAccount]:
        try:
            users = _content(await self.connector.get_json(self.service, "/api/v1/users"))
        except ProviderAuthError:
            users = []
        if not users:  # not an administrator: only the configured account is known
            username = str(self.service.config.get("username", ""))
            return [ServiceAccount(await self.connector.self_id(self.service), username, username)]
        return [
            ServiceAccount(
                external_id=str(u["id"]),
                username=u.get("username") or None,
                display_name=u.get("name") or u.get("username") or None,
                email=u.get("email") or None,
            )
            for u in users
            if u.get("id") is not None
        ]
