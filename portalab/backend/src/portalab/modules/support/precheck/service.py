"""Precheck (T028; R7): before a ticket, show open incidents that match the chosen service or the text and
permitted wiki suggestions (``support.knowledge``) — deterministic, no AI. Each section answers on its own
(``ok|unavailable``) so a wiki outage never blocks the ticket form."""

import asyncio
from typing import Any

from portalab.capabilities.content import KNOWLEDGE
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.support.incidents.service import IncidentService
from portalab.modules.support.permissions import INCIDENTS_READ


class Precheck:
    def __init__(
        self,
        incidents: IncidentService,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        config: Any,
    ) -> None:
        self.incidents = incidents
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.config = config

    async def incidents_for(self, principal: Principal, service_id: str | None, text: str) -> dict[str, Any]:
        try:
            if not await self.authorizer.is_allowed(principal, INCIDENTS_READ):
                return {"state": "ok", "items": []}
            views = await self.incidents.list(state="open", limit=100)
        except Exception:
            return {"state": "unavailable", "items": []}
        mode = self.config().incident_precheck_match_mode
        words = [w for w in normalize_for_search(text).split() if len(w) > 3]
        items = []
        for view in views:
            by_service = bool(service_id) and service_id in view.service_ids
            haystack = normalize_for_search(f"{view.title} {view.summary}")
            by_text = bool(words) and sum(1 for w in words if w in haystack) >= min(2, len(words))
            match = (
                by_service or by_text
                if mode == "service_or_text"
                else by_service
                if mode == "service"
                else by_text
            )
            if match:
                items.append(
                    {
                        "id": str(view.id),
                        "reference": view.reference,
                        "title": view.title,
                        "severity": view.severity,
                        "state": view.state,
                        "url": f"/incidents/{view.id}",
                    }
                )
        return {"state": "ok", "items": items[:5]}

    async def knowledge_for(self, principal: Principal, text: str) -> dict[str, Any]:
        if not text.strip():
            return {"state": "ok", "items": []}
        try:
            providers = self.capabilities.system_providers(KNOWLEDGE)
        except Exception:
            providers = []
        if not providers:
            return {"state": "unavailable", "items": []}
        try:
            hits = await asyncio.wait_for(providers[0].provider.search(text, principal, limit=5), timeout=3)
        except Exception:
            return {"state": "unavailable", "items": []}
        return {
            "state": "ok",
            "items": [{"title": h.title, "excerpt": h.excerpt, "url": h.url} for h in hits],
        }

    async def run(self, principal: Principal, service_id: str | None, text: str) -> dict[str, Any]:
        incidents, knowledge = await asyncio.gather(
            self.incidents_for(principal, service_id, text), self.knowledge_for(principal, text)
        )
        return {"incidents": incidents, "knowledge": knowledge}
