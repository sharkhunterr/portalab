"""``SearchAssistant`` for 008 (T028): ``stream`` synthesizes over the **already permitted** result
references (re-hydrated as the principal), read-only tools only; ``source_ref`` events name only those
references, ``synthesis`` is labelled interpretation. ``interpret`` turns free text into navigation/search
suggestions validated against the user's own navigation (unknown routes are dropped by 008 too)."""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Sequence
from typing import Any

from portalab.capabilities.ai import ChatMessage, SourceRef, ToolResult
from portalab.capabilities.search import AssistEvent, IntentSuggestion, SearchRegistry, default_search
from portalab.core.authz_port import Principal
from portalab.modules.ai.context import frame_tool_result, system_prompt
from portalab.modules.ai.observability import log
from portalab.modules.ai.orchestrator import Orchestrator
from portalab.modules.ai.principal import ai_principal, subject_of
from portalab.modules.ai.tools.catalog import NO_TOOLS, READ_ONLY, ToolPolicy

SEARCH_POLICY = ToolPolicy(
    "search_assist", READ_ONLY.sensitivities, frozenset({"wiki.search", "services.status"})
)
JSON_ARRAY = re.compile(r"\[.*\]", re.S)


class SearchAssistantFacade:
    def __init__(self, orchestrator: Orchestrator, search: SearchRegistry = default_search) -> None:
        self.orchestrator = orchestrator
        self.search = search

    async def _hydrate(
        self, principal: Principal, refs: Sequence[tuple[str, str]]
    ) -> list[tuple[str, str, str]]:
        by_kind: dict[str, list[str]] = {}
        for kind, item_id in refs[:20]:
            by_kind.setdefault(kind, []).append(item_id)
        found: list[tuple[str, str, str]] = []
        for kind, ids in by_kind.items():
            provider = self.search.provider(kind)
            if provider is None:
                continue
            try:
                items = await asyncio.wait_for(provider.hydrate(ids, ai_principal(principal)), timeout=3)
            except Exception:
                log.warning("assist references not hydrated", extra={"fields": {"kind": kind}})
                continue
            found.extend((i.kind, i.id, i.title) for i in items)
        return found

    async def stream(
        self, query: str, principal: Principal, result_refs: Sequence[tuple[str, str]]
    ) -> AsyncIterator[AssistEvent]:
        items = await self._hydrate(principal, result_refs)
        seeds = [SourceRef(kind, f"{kind}:{item_id}", title, "real") for kind, item_id, title in items]
        numbered = [
            {"n": n, "title": title, "kind": kind} for n, (kind, _, title) in enumerate(items, start=1)
        ]
        user = subject_of(principal)
        language = await self.orchestrator.language_for(user)
        results = frame_tool_result("search.results", ToolResult("ok", {"results": numbered}), [])
        messages = [
            ChatMessage("system", system_prompt(language, None)),
            ChatMessage(
                "user",
                f"Search: {json.dumps(query[:256])}\n{results}\n"
                "Summarize what these results say about the search; cite them by number.",
            ),
        ]
        by_number = {n: (kind, item_id) for n, (kind, item_id, _) in enumerate(items, start=1)}
        async for event in self.orchestrator.run(
            principal, messages, policy=SEARCH_POLICY, seed_sources=seeds
        ):
            if event["event"] == "delta":
                yield AssistEvent("synthesis", {"text": event["data"]["text"]})
            elif event["event"] == "error":
                yield AssistEvent("error", {"code": "search.assist_failed"})
                return
            elif event["event"] == "done":
                for source in event["data"]["sources"]:
                    ref = by_number.get(int(source["n"]))
                    if ref is not None:
                        yield AssistEvent("source_ref", {"kind": ref[0], "id": ref[1], "n": source["n"]})

    async def interpret(
        self, text: str, principal: Principal, page_context: str | None
    ) -> Sequence[IntentSuggestion]:
        user = subject_of(principal)
        language = await self.orchestrator.language_for(user)
        messages = [
            ChatMessage("system", system_prompt(language, {"route": page_context} if page_context else None)),
            ChatMessage(
                "user",
                "Turn this request into at most 3 suggestions as a JSON array of objects with keys "
                "label, route (a portal path or null) and query (a search or null). "
                f"Request: {json.dumps(text[:300])}",
            ),
        ]
        try:
            outcome = await self.orchestrator.complete(principal, messages, policy=NO_TOOLS)
        except Exception:
            return []
        return parse_suggestions(outcome.content)


def parse_suggestions(content: str) -> list[IntentSuggestion]:
    match = JSON_ARRAY.search(content)
    if match is None:
        return []
    try:
        raw: Any = json.loads(match.group(0))
    except ValueError:
        return []
    out: list[IntentSuggestion] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("label"), str):
            continue
        route = item.get("route")
        query = item.get("query")
        out.append(
            IntentSuggestion(
                label=item["label"][:120],
                route=route
                if isinstance(route, str) and route.startswith("/") and not route.startswith("//")
                else None,
                query=query[:200] if isinstance(query, str) else None,
            )
        )
    return out[:5]
