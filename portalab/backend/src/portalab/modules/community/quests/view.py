"""Quests view (T020; US4, slice C): the viewer's **own** quests, daily objectives and challenges from 013
(``economy.catalog``) — a challenge is shown as a time-boxed quest (its window end). Progress is never shown
for anyone else."""

from typing import Any

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.modules.community.achievements.view import CatalogView, catalog
from portalab.modules.community.observability import log, metrics

FIELDS = (
    "key",
    "kind",
    "label",
    "description",
    "icon",
    "period",
    "period_key",
    "starts_at",
    "ends_at",
    # #307: its texts in other languages, when it starts again, how it completes, when it was done
    "translations",
    "resets_at",
    "complete_on",
    "completed_at",
    "gifts",
)


class QuestsView:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def mine(self, viewer: Principal) -> CatalogView:
        user = viewer.acting_for or viewer.user_id
        source = catalog(self.capabilities)
        if user is None or source is None:
            return CatalogView("unavailable")
        try:
            raw = await source.quests_of(user)
        except Exception as error:
            metrics.increment("community.quests.unavailable")
            log.warning("quests unavailable", extra={"error": type(error).__name__})
            return CatalogView("unavailable")
        items: list[dict[str, Any]] = []
        for quest in raw:
            item = {k: quest.get(k) for k in FIELDS}
            item["time_boxed"] = quest.get("kind") == "challenge" or bool(quest.get("ends_at"))
            item["completed"] = quest.get("completed_at") is not None
            item["steps"] = [
                {"current": int(s.get("current", 0)), "target": int(s.get("target", 1))}
                for s in quest.get("steps", [])
            ]
            item["rewards"] = list(quest.get("rewards", []))
            items.append(item)
        return CatalogView("available" if items else "no-data", items)
