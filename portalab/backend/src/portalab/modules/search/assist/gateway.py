"""``AssistGateway`` (T019; R5, R6): the AI analysis is a **separate stream** (``POST /search/assist``,
SSE) bridging the ``SearchAssistant`` port (spec 018). It shares no failure path with ``/search``:

* without an assistant the stream says ``unavailable`` and ends — classic search is unaffected;
* result references sent by the client are re-hydrated through their (permitted) providers first, so the
  assistant only ever receives what the principal may see (CD-003, FR-017) — a classic-search failure
  just means fewer references, never no answer;
* events are typed ``source_ref`` (real data) vs ``synthesis`` (interpretation) so the UI can tell them
  apart (FR-005); a ``source_ref`` the assistant invents for an unknown item is dropped.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import ASSISTANT, AssistEvent
from portalab.core.authz_port import Principal
from portalab.modules.search.coordinator.coordinator import SearchCoordinator
from portalab.modules.search.observability import log, metrics

MAX_REFS = 50


def sse(event: AssistEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(dict(event.data), ensure_ascii=False)}\n\n"


class AssistGateway:
    def __init__(self, capabilities: CapabilityRegistry, coordinator: SearchCoordinator) -> None:
        self.capabilities = capabilities
        self.coordinator = coordinator

    def assistant(self) -> Any | None:
        providers = self.capabilities.system_providers(ASSISTANT)
        return providers[0].provider if providers else None

    async def permitted_refs(
        self, principal: Principal, refs: Sequence[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        by_kind: dict[str, list[str]] = {}
        for kind, item_id in refs[:MAX_REFS]:
            by_kind.setdefault(kind, []).append(item_id)
        kept: list[tuple[str, str]] = []
        for provider in await self.coordinator.permitted(principal, list(by_kind)):
            try:
                items = await asyncio.wait_for(provider.hydrate(by_kind[provider.kind], principal), timeout=2)
            except Exception:
                log.warning("search source refused assist references", extra={"kind": provider.kind})
                continue
            kept.extend((item.kind, item.id) for item in items)
        return kept

    async def stream(
        self, query: str, principal: Principal, refs: Sequence[tuple[str, str]]
    ) -> AsyncIterator[str]:
        assistant = self.assistant()
        if assistant is None:
            yield sse(AssistEvent("status", {"state": "unavailable"}))
            return
        allowed = await self.permitted_refs(principal, refs)
        allowed_set = set(allowed)
        yield sse(AssistEvent("status", {"state": "started", "sources": len(allowed)}))
        try:
            async for event in assistant.stream(query, principal, allowed):
                if event.type == "source_ref":
                    ref = (str(event.data.get("kind", "")), str(event.data.get("id", "")))
                    if ref not in allowed_set:
                        continue  # only real, permitted results may be presented as sources
                yield sse(event)
        except asyncio.CancelledError:
            raise  # client went away: stop cleanly
        except Exception:
            log.warning("search assistant failed")
            metrics.increment("search.assist.failures")
            yield sse(AssistEvent("error", {"code": "search.assist_failed"}))
            return
        yield sse(AssistEvent("status", {"state": "done"}))
