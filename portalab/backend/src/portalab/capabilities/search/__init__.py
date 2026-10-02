"""Search SDK (spec 008 T007; contracts/search-contracts.md): what a domain module (or plugin) implements to
take part in global search and the command palette.

* ``SearchProvider`` — one *kind* (``users``, ``services``, ``wiki``…): searches **its own tables** with the
  principal's authorization and visibility applied *inside* the query (permission at source, CD-002/016) and
  re-authorizes ids in ``hydrate`` (semantic candidates, object references);
* ``Indexable`` (optional) — documents for the semantic index (ids + text in, vectors out;
  never authoritative);
* ``ObjectResolver`` — opens an object from a palette reference (``#123``, ``portalab://kind/id``);
* ports implemented elsewhere: ``EmbeddingProvider`` (optional, none by default) and ``SearchAssistant``
  (AI, spec 018) — search never depends on them.

Registrations are owner-tagged so a disabled plugin's contributions disappear with ``unregister(owner)``
(spec 023 conformance sweep, F20).
"""

from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

EMBEDDING = "search.embedding"
ASSISTANT = "search.assistant"

Mode = Literal["exact", "semantic", "mixed"]
GroupState = Literal["ok", "partial", "unavailable"]
MatchedBy = Literal["exact", "semantic"]
Sensitivity = Literal["normal", "sensitive", "destructive"]


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    """A user query after parsing (``QueryParser``): free text, typed filters and mode — never SQL."""

    text: str  # free text, length-capped, filters removed
    normalized: str  # ``normalize_for_search(text)`` (NFKC, casefold, diacritics folded)
    terms: tuple[str, ...]  # normalized words, for highlighting and trigram matching
    mode: Mode = "mixed"
    filters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    date_from: datetime | None = None  # inclusive, UTC (relative dates resolved with the user's zone)
    date_to: datetime | None = None  # exclusive, UTC
    language: str | None = None
    kinds: tuple[str, ...] | None = None  # restrict to these kinds (``type:`` filter or API ``kinds``)


@dataclass(frozen=True, slots=True)
class Segment:
    """A piece of a snippet: plain text (rendered as text, never markup) and whether it matched."""

    text: str
    hit: bool = False


@dataclass(frozen=True, slots=True)
class SearchItem:
    kind: str
    id: str
    title: str
    url_ref: str  # SPA route (``/services/…``) or ``portalab://kind/id``
    snippet: tuple[Segment, ...] = ()
    language: str | None = None
    matched_by: MatchedBy = "exact"
    score: float = 0.0
    facets: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FacetDef:
    key: str  # filter name (``state``, ``connector``…)
    label_key: str
    kind: Literal["enum", "date", "text"] = "enum"
    values: tuple[str, ...] = ()  # allowed values for ``enum`` (empty: any)


@dataclass(frozen=True, slots=True)
class ProviderResult:
    items: Sequence[SearchItem] = ()
    state: GroupState = "ok"
    next_cursor: str | None = None
    facets: Mapping[str, Mapping[str, int]] = field(default_factory=dict)  # counts over *permitted* items
    took_ms: int = 0


@runtime_checkable
class SearchProvider(Protocol):
    kind: str
    label_key: str
    required_permission: str

    def facets(self) -> Sequence[FacetDef]: ...

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult: ...

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        """Items for ``ids`` the principal may see *now*; others are silently dropped."""
        ...


@dataclass(frozen=True, slots=True)
class IndexDocument:
    id: str
    language: str | None
    text: str
    content_hash: str


@runtime_checkable
class Indexable(Protocol):
    def documents(self, since: datetime | None) -> AsyncIterator[IndexDocument]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_id: str
    dimension: int

    async def embed(self, texts: Sequence[str], language: str | None) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True, slots=True)
class AssistEvent:
    """``source_ref`` = a real result the principal may see; ``synthesis`` = interpretation (FR-005)."""

    type: Literal["source_ref", "synthesis", "status", "error"]
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntentSuggestion:
    label: str
    route: str | None = None
    command_key: str | None = None
    query: str | None = None


@runtime_checkable
class SearchAssistant(Protocol):
    def stream(
        self, query: str, principal: Principal, result_refs: Sequence[tuple[str, str]]
    ) -> AsyncIterator[AssistEvent]: ...

    async def interpret(
        self, text: str, principal: Principal, page_context: str | None
    ) -> Sequence[IntentSuggestion]: ...


@dataclass(frozen=True, slots=True)
class ActionDef:
    """A palette action (from a 004 ``NavigationContribution(kind=command)``), as offered to a principal."""

    id: str
    label_key: str
    permission: str
    sensitivity: Sensitivity = "normal"
    route: str | None = None
    action_id: str | None = None
    confirmation_required: bool = False
    keywords: tuple[str, ...] = ()
    context_route: str | None = None  # offered only on this page (prefix match)


@dataclass(frozen=True, slots=True)
class ObjectRef:
    kind: str
    id: str
    title: str
    route: str


@runtime_checkable
class ObjectResolver(Protocol):
    kind: str
    prefixes: tuple[str, ...]  # short-reference prefixes handled (``#`` for tickets, ``svc:``…)

    async def resolve(self, ref: str, principal: Principal) -> ObjectRef | None:
        """The object if it exists **and** the principal may see it, else ``None`` (reveal nothing)."""
        ...


class SearchRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _Owned:
    owner: str
    value: Any


class SearchRegistry:
    """Providers (one per kind), object resolvers and context actions — owner-tagged (F20)."""

    def __init__(self) -> None:
        self._providers: dict[str, _Owned] = {}
        self._resolvers: dict[str, _Owned] = {}
        self._actions: dict[str, _Owned] = {}

    def register(self, provider: SearchProvider, *, owner: str) -> None:
        kind = provider.kind
        if owner.startswith("plugin:") and not kind.startswith(f"plugin:{owner.removeprefix('plugin:')}"):
            raise SearchRegistryError(f"plugin kinds are namespaced 'plugin:<key>' ({kind!r})")
        existing = self._providers.get(kind)
        if existing is not None and existing.owner != owner:
            raise SearchRegistryError(f"search kind {kind!r} is already provided by {existing.owner}")
        self._providers[kind] = _Owned(owner, provider)

    def register_resolver(self, resolver: ObjectResolver, *, owner: str) -> None:
        self._resolvers[resolver.kind] = _Owned(owner, resolver)

    def register_action(self, action: ActionDef, *, owner: str) -> None:
        self._actions[action.id] = _Owned(owner, action)

    def providers(self, kinds: Iterable[str] | None = None) -> list[SearchProvider]:
        wanted = None if kinds is None else set(kinds)
        return [
            entry.value for kind, entry in sorted(self._providers.items()) if wanted is None or kind in wanted
        ]

    def provider(self, kind: str) -> SearchProvider | None:
        entry = self._providers.get(kind)
        return entry.value if entry else None

    def resolvers(self) -> list[ObjectResolver]:
        return [entry.value for _, entry in sorted(self._resolvers.items())]

    def actions(self) -> list[ActionDef]:
        return [entry.value for _, entry in sorted(self._actions.items())]

    def unregister(self, owner: str) -> int:
        removed = 0
        for table in (self._providers, self._resolvers, self._actions):
            for key in [k for k, entry in table.items() if entry.owner == owner]:
                del table[key]
                removed += 1
        return removed


default_search = SearchRegistry()


def register_provider(provider: SearchProvider, *, owner: str) -> None:
    default_search.register(provider, owner=owner)


EMBEDDING_SPEC = CapabilitySpec(
    name=EMBEDDING,
    version="1.0",
    protocol=EmbeddingProvider,
    multi_provider=False,
    description="Optional text embeddings for semantic search (none by default).",
)
ASSISTANT_SPEC = CapabilitySpec(
    name=ASSISTANT,
    version="1.0",
    protocol=SearchAssistant,
    multi_provider=False,
    description="AI analysis over permitted search results and palette interpretation (spec 018).",
)
SPECS: tuple[CapabilitySpec, ...] = (EMBEDDING_SPEC, ASSISTANT_SPEC)
