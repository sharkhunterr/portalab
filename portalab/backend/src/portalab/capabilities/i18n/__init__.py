"""i18n contracts (spec 026, contracts/i18n-contracts.md) consumed by every module.

* :class:`LocaleContext` — resolved language ⟂ locale ⟂ time zone (+ direction, fallback chain, hour cycle,
  first day of week); immutable.
* Protocols for the resolver, message renderer, formatter, time renderer and content localizer, provided by
  the ``i18n`` module through the capability registry.
* :func:`normalize_for_search` (pure; consumed by 008) and the optional :class:`TranslationProvider` port.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

RESOLVER = "i18n.resolver"
RENDERER = "i18n.renderer"
FORMATTER = "i18n.formatter"
TIME = "i18n.time"
CONTENT = "i18n.content"

Direction = Literal["ltr", "rtl"]
ContentState = Literal["source", "translated", "untranslated", "machine_draft"]


@dataclass(frozen=True, slots=True)
class LocaleContext:
    language: str = "en"
    locale: str = "en"
    time_zone: str = "UTC"
    direction: Direction = "ltr"
    fallback_chain: tuple[str, ...] = ("en",)
    hour_cycle: Literal["h12", "h23"] | None = None
    first_day_of_week: int | None = None  # 0 = Monday … 6 = Sunday; None = locale default
    retained_language: str | None = None  # the user's preference kept while policy hides it

    def as_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "locale": self.locale,
            "time_zone": self.time_zone,
            "direction": self.direction,
            "fallback_chain": list(self.fallback_chain),
            "hour_cycle": self.hour_cycle,
            "first_day_of_week": self.first_day_of_week,
            "retained_language": self.retained_language,
        }


DEFAULT_CONTEXT = LocaleContext()


@runtime_checkable
class LocaleResolverPort(Protocol):
    async def for_user(self, user_id: UUID | None) -> LocaleContext: ...


@runtime_checkable
class MessageRendererPort(Protocol):
    def t(
        self, key: str, ctx: LocaleContext, args: Mapping[str, Any] | None = None, *, namespace: str = "core"
    ) -> str: ...


@runtime_checkable
class FormatterPort(Protocol):
    def number(self, value: float, ctx: LocaleContext) -> str: ...

    def date(self, value: date | datetime, ctx: LocaleContext, style: str = "medium") -> str: ...

    def time(self, value: datetime, ctx: LocaleContext, style: str = "short") -> str: ...

    def relative(self, seconds: float, ctx: LocaleContext) -> str: ...


@runtime_checkable
class TimeRendererPort(Protocol):
    def render_instant(self, instant: datetime, ctx: LocaleContext, style: str = "medium") -> str: ...

    def resolve_wall_clock(self, local: datetime, time_zone: str, policy: str | None = None) -> datetime: ...


@dataclass(frozen=True, slots=True)
class LocalizedContent:
    content_kind: str
    content_id: str
    language: str
    version: int
    state: ContentState
    is_fallback: bool
    source_language: str


@runtime_checkable
class ContentLocalizerPort(Protocol):
    async def get(
        self, content_kind: str, content_id: str, ctx: LocaleContext
    ) -> LocalizedContent | None: ...


@dataclass(frozen=True, slots=True)
class Translation:
    text: str
    language: str
    provider: str
    machine: bool = True
    extra: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class TranslationProvider(Protocol):
    """Optional presentation-layer translation (no default implementation; off unless configured)."""

    async def translate(
        self, text: str, source_language: str | None, target_language: str
    ) -> Translation: ...


def normalize_for_search(text: str, language: str | None = None) -> str:
    """NFKC, casefold and diacritics folding (``é`` → ``e``, ``ß`` → ``ss``) for language-aware matching."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    decomposed = unicodedata.normalize("NFD", folded)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    if language and language.split("-")[0] == "tr":
        stripped = stripped.replace("\u0131", "i")  # dotless i folds to i for Turkish
    return unicodedata.normalize("NFC", stripped)


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=False, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(RESOLVER, LocaleResolverPort, "Locale resolution per user (026)"),
    _spec(RENDERER, MessageRendererPort, "ICU message rendering with fallback (026)"),
    _spec(FORMATTER, FormatterPort, "CLDR formatting (026)"),
    _spec(TIME, TimeRendererPort, "Time zone rendering and wall-clock resolution (026)"),
    _spec(CONTENT, ContentLocalizerPort, "Multilingual content versions (026)"),
)
