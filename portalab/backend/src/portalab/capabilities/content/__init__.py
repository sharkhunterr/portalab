"""Content contracts shared by News, Wiki and Calendar (spec 011, contracts/content-contracts.md).

* ``ContentRef`` — opaque cross-domain references ``portalab://<kind>/<id>`` (no foreign keys);
* ``LinkResolver`` registry — each domain answers, **per viewer**, ``ok|forbidden|archived|deleted|
  unavailable`` (a title only when the viewer may see it);
* ``CalendarSource`` registry — owners (News, Health maintenance, campaigns…) provide dated items with the
  permission applied at the source; the calendar owns no item;
* ``support.knowledge`` / ``content.help`` ports — principal-bounded knowledge for Support, AI and the
  contextual help slot.
Registries are owner-tagged: ``unregister(owner)`` removes every contribution of a module or plugin.
"""

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

KNOWLEDGE = "support.knowledge"
HELP = "content.help"
LinkState = Literal["ok", "forbidden", "archived", "deleted", "unavailable"]
ItemType = Literal["event", "maintenance", "campaign", "community_event", "deadline", "publication"]
SourceState = Literal["ok", "partial", "unavailable"]
_REF = re.compile(r"^portalab://([a-z][a-z0-9_.-]{0,40})/([A-Za-z0-9_.:/-]{1,200})$")


class ContentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContentRef:
    kind: str
    id: str

    @classmethod
    def parse(cls, value: str) -> "ContentRef":
        match = _REF.match(value.strip())
        if not match:
            raise ContentError(f"not a content ref: {value!r}")
        return cls(match.group(1), match.group(2))

    def format(self) -> str:
        return f"portalab://{self.kind}/{self.id}"


@dataclass(frozen=True, slots=True)
class ResolvedLink:
    ref: str
    state: LinkState
    title: str | None = None
    url: str | None = None


@runtime_checkable
class LinkResolver(Protocol):
    kind: str

    async def resolve(self, refs: Sequence[ContentRef], viewer: Principal) -> dict[str, ResolvedLink]:
        """State per formatted ref; a forbidden target never carries a title."""
        ...


class LinkResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, tuple[LinkResolver, str]] = {}

    def register(self, resolver: LinkResolver, *, owner: str) -> None:
        existing = self._resolvers.get(resolver.kind)
        if existing is not None and existing[1] != owner:
            raise ContentError(f"link kind {resolver.kind!r} belongs to {existing[1]}")
        self._resolvers[resolver.kind] = (resolver, owner)

    def get(self, kind: str) -> LinkResolver | None:
        entry = self._resolvers.get(kind)
        return entry[0] if entry else None

    def kinds(self) -> list[str]:
        return sorted(self._resolvers)

    def unregister(self, owner: str) -> int:
        doomed = [k for k, (_, who) in self._resolvers.items() if who == owner]
        for key in doomed:
            del self._resolvers[key]
        return len(doomed)


default_link_resolvers = LinkResolverRegistry()


# --- calendar --------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CalendarItem:
    source_kind: str
    source_id: str
    type: ItemType
    title: str
    starts_at: datetime | None = None  # UTC instant (None for all-day items)
    ends_at: datetime | None = None
    date: dt.date | None = None  # all-day items
    all_day: bool = False
    reference_tz: str | None = None
    status: str = "scheduled"
    url_ref: str | None = None  # SPA route or ``portalab://`` ref


@dataclass(frozen=True, slots=True)
class CalendarSourceResult:
    items: Sequence[CalendarItem] = ()
    state: SourceState = "ok"
    as_of: datetime | None = None


@runtime_checkable
class CalendarSource(Protocol):
    kind: str
    label_key: str

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult: ...

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        """One item as the viewer may see it now (reminders re-check it at fire time)."""
        ...


class CalendarSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, tuple[CalendarSource, str]] = {}

    def register(self, source: CalendarSource, *, owner: str) -> None:
        existing = self._sources.get(source.kind)
        if existing is not None and existing[1] != owner:
            raise ContentError(f"calendar source {source.kind!r} belongs to {existing[1]}")
        self._sources[source.kind] = (source, owner)

    def get(self, kind: str) -> CalendarSource | None:
        entry = self._sources.get(kind)
        return entry[0] if entry else None

    def all(self) -> list[CalendarSource]:
        return [self._sources[k][0] for k in sorted(self._sources)]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, (_, who) in self._sources.items() if who == owner]
        for key in doomed:
            del self._sources[key]
        return len(doomed)


default_calendar_sources = CalendarSourceRegistry()


# --- knowledge / help -------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    ref: str  # ``portalab://wiki/<id>``
    title: str
    excerpt: str
    url: str
    score: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class KnowledgeProvider(Protocol):
    async def search(
        self, text: str, principal: Principal, *, limit: int = 5, for_ai: bool = False
    ) -> Sequence[KnowledgeHit]:
        """Pages the principal may read (``for_ai`` → only pages marked readable by AI)."""
        ...


@runtime_checkable
class HelpResolver(Protocol):
    async def for_context(self, key: str, principal: Principal) -> Sequence[KnowledgeHit]: ...


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=False, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(KNOWLEDGE, KnowledgeProvider, "Principal-bounded knowledge search (Wiki, 011)"),
    _spec(HELP, HelpResolver, "Contextual help pages for a UI key (Wiki, 011)"),
)
