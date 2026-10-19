"""Catalogs (T017; R6, FR-011..013): effective catalog = base bundle files (``backend/locales/<lang>/
<namespace>.json``, plus plugin bundles) ⊕ published admin overrides (``i18n.catalog_entries``), versioned
by a content hash (ETag). Lookups walk the fallback chain; a missing key renders the fallback value (or
the key itself), is counted in ``missing_key_stats`` and never raises."""

import asyncio
import contextlib
import hashlib
import json
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.i18n import LocaleContext, SiteTerms, SiteTermsPort
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.i18n.catalog.plugins import PluginCatalogs, default_plugin_catalogs
from portalab.modules.i18n.catalog.terms import rewrite_all
from portalab.modules.i18n.models import CatalogEntry, MissingKeyStat
from portalab.modules.i18n.observability import metrics
from portalab.modules.i18n.render.icu import MessageSyntaxError, render

LOCALES_DIR = Path(__file__).resolve().parents[5] / "locales"
NAMESPACE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-.")


def valid_namespace(namespace: str) -> bool:
    return bool(namespace) and len(namespace) <= 64 and set(namespace) <= NAMESPACE_CHARS


class CatalogService:
    def __init__(
        self,
        database: Database,
        *,
        locales_dir: Path = LOCALES_DIR,
        plugins: PluginCatalogs = default_plugin_catalogs,
        clock: Clock | None = None,
        terms: Callable[[], SiteTermsPort | None] | None = None,
    ) -> None:
        self.database = database
        self.locales_dir = locales_dir
        self.plugins = plugins
        self.clock = clock
        self.terms = terms  # issue 159: the site's name and currency, written into every message
        self._overrides: dict[tuple[str, str], dict[str, str]] = {}
        self._loaded = False
        self._missing: Counter[tuple[str, str, str]] = Counter()
        self._lock = threading.Lock()

    # --- base & overrides ---------------------------------------------------------------------------
    def base(self, namespace: str, language: str) -> dict[str, str]:
        if not valid_namespace(namespace):
            return {}
        merged: dict[str, str] = {}
        path = self.locales_dir / language / f"{namespace}.json"
        if path.is_file():
            try:
                merged.update(
                    {str(k): str(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
                )
            except (ValueError, OSError):
                metrics.increment("i18n.bundle_load_failures")
        merged.update(self.plugins.messages(namespace, language))
        return merged

    def namespaces(self) -> list[str]:
        found = {p.stem for p in self.locales_dir.glob("*/*.json")} | self.plugins.namespaces()
        return sorted(found)

    async def reload_overrides(self) -> None:
        async with self.database.session() as session:
            await self.reload_overrides_in(session)

    async def reload_overrides_in(self, session: Any) -> None:
        rows = (
            await session.execute(select(CatalogEntry).where(CatalogEntry.state == "published"))
        ).scalars()
        overrides: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            overrides.setdefault((row.namespace, row.language), {})[row.key] = row.message
        self._overrides = overrides
        self._loaded = True

    async def ensure_loaded(self) -> None:
        if not self._loaded:
            try:
                await self.reload_overrides()
            except Exception:
                self._loaded = True  # serve the base bundles if the store is down
        source = self._terms_source()
        if source is not None:
            with contextlib.suppress(Exception):
                await source.refresh()

    async def keep_fresh(self, stop: asyncio.Event | None = None, interval: float = 30.0) -> None:
        """For a process that renders without serving the catalogs (the worker's e-mails): the published
        overrides and the site's words read again every ``interval`` seconds, until ``stop``."""
        while stop is None or not stop.is_set():
            with contextlib.suppress(Exception):
                await self.reload_overrides()
            source = self._terms_source()
            if source is not None:
                with contextlib.suppress(Exception):
                    await source.refresh()
            if stop is None:
                await asyncio.sleep(interval)
            else:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=interval)

    def _terms_source(self) -> SiteTermsPort | None:
        try:
            return self.terms() if self.terms is not None else None
        except Exception:
            return None

    def effective(self, namespace: str, language: str) -> dict[str, str]:
        merged = {**self.base(namespace, language), **self._overrides.get((namespace, language), {})}
        source = self._terms_source()
        if source is None:
            return merged
        try:
            terms = source.terms(language)
        except Exception:
            terms = SiteTerms()
        return rewrite_all(namespace, merged, terms)

    def bundle(self, namespace: str, ctx: LocaleContext) -> tuple[dict[str, str], str]:
        """Merged messages for the context's fallback chain (most preferred wins) and their version hash."""
        merged: dict[str, str] = {}
        for language in reversed(_chain(ctx)):
            merged.update(self.effective(namespace, language))
        version = hashlib.sha256(json.dumps(merged, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[
            :20
        ]
        return merged, version

    # --- rendering ----------------------------------------------------------------------------------
    def lookup(self, namespace: str, key: str, ctx: LocaleContext) -> tuple[str | None, str | None]:
        for language in _chain(ctx):
            message = self.effective(namespace, language).get(key)
            if message is not None:
                if language != ctx.language:
                    self._count_missing(namespace, ctx.language, key)
                return message, language
        self._count_missing(namespace, ctx.language, key)
        return None, None

    def t(
        self, key: str, ctx: LocaleContext, args: Mapping[str, Any] | None = None, *, namespace: str = "core"
    ) -> str:
        message, language = self.lookup(namespace, key, ctx)
        if message is None:
            return key
        try:
            return render(
                message, args or {}, ctx.locale if language == ctx.language else language or ctx.locale
            )
        except MessageSyntaxError:
            metrics.increment("i18n.invalid_messages")
            return key

    def _count_missing(self, namespace: str, language: str, key: str) -> None:
        with self._lock:
            self._missing[(namespace, language, key[:160])] += 1
        metrics.increment("i18n.fallbacks")

    async def flush_missing(self) -> int:
        with self._lock:
            drained, self._missing = self._missing, Counter()
        if not drained:
            return 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for (namespace, language, key), count in drained.items():
                await uow.session.execute(
                    insert(MissingKeyStat)
                    .values(
                        namespace=namespace,
                        language=language,
                        key=key,
                        count=count,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["namespace", "language", "key"],
                        set_={"count": MissingKeyStat.count + count, "last_seen_at": now},
                    )
                )
        return len(drained)


def _chain(ctx: LocaleContext) -> list[str]:
    chain: list[str] = []
    for language in (ctx.language, *ctx.fallback_chain, "en"):
        if language not in chain:
            chain.append(language)
        base = language.split("-")[0]
        if base not in chain:
            chain.append(base)
    return chain


def placeholders(messages: Iterable[str]) -> set[str]:
    from portalab.modules.i18n.render.icu import arguments_of, parse

    names: set[str] = set()
    for message in messages:
        names |= arguments_of(parse(message))
    return names
