"""``VisibilityFilter`` implementation (T011) — the port declared by spec 003, applied after ``require()``."""

from typing import Any
from uuid import UUID

from portalab.capabilities.visibility import Level
from portalab.core.authz_port import Principal
from portalab.core.visibility_port import Redacted
from portalab.modules.privacy.observability import metrics
from portalab.modules.privacy.visibility.levels import Surface, relation_of, visible
from portalab.modules.privacy.visibility.service import VisibilityService


class PrivacyVisibilityFilter:
    def __init__(self, service: VisibilityService) -> None:
        self.service = service

    async def filter(
        self,
        viewer: Principal,
        subject: UUID,
        datum_class: str,
        datum_ref: str | None,
        value: Any,
        surface: Surface = "profile",
    ) -> Any | Redacted:
        relation = relation_of(viewer, subject)
        if relation == "self":
            return value
        level = await self.service.effective_level(subject, datum_class, datum_ref)
        shown = visible(level, relation, surface)
        metrics.increment(f"privacy.visibility.{level}.{'shown' if shown else 'hidden'}")
        return value if shown else Redacted(datum_class)

    async def effective_level(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level:
        return await self.service.effective_level(subject, datum_class, datum_ref)
