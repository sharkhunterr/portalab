"""Profile assembler (T007; US1, R3): a community profile is a list of registered sections, each governed
by a 021 datum class of the profile owner and a permission of the viewer. A section the viewer may not see
is **absent** (never "hidden"); each section is computed independently — a failing or slow provider makes
that one section ``unavailable`` and never breaks the page."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from portalab.capabilities.community import ProfileSection, SectionRegistry, SectionResult
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.community.observability import log, metrics
from portalab.modules.community.preferences import shown

SECTION_TIMEOUT_S = 3.0


@dataclass(frozen=True, slots=True)
class AssembledSection:
    key: str
    owner: str
    label_key: str
    order: int
    result: SectionResult


class ProfileAssembler:
    def __init__(
        self, sections: SectionRegistry, visibility: VisibilityFilter, authorizer: Authorizer
    ) -> None:
        self.sections = sections
        self.visibility = visibility
        self.authorizer = authorizer

    async def visible(self, viewer: Principal, owner: UUID) -> list[ProfileSection]:
        out: list[ProfileSection] = []
        for section in self.sections.all():
            if not await self.authorizer.is_allowed(viewer, section.permission):
                continue
            if await shown(self.visibility, viewer, owner, section.datum_class, True):
                out.append(section)
        return out

    async def compute(self, section: ProfileSection, viewer: Principal, owner: UUID) -> SectionResult:
        try:
            result = await asyncio.wait_for(section.provider(owner, viewer), SECTION_TIMEOUT_S)
        except Exception as error:  # one section's failure stays in that section
            metrics.increment("community.section.failed")
            log.warning(
                "profile section failed", extra={"section": section.key, "error": type(error).__name__}
            )
            return SectionResult("unavailable")
        return result if isinstance(result, SectionResult) else SectionResult("unavailable")

    async def profile(self, viewer: Principal, owner: UUID) -> list[AssembledSection]:
        sections = await self.visible(viewer, owner)
        results = await asyncio.gather(*(self.compute(s, viewer, owner) for s in sections))
        return [
            AssembledSection(s.key, s.owner, s.label_key, s.order, r)
            for s, r in zip(sections, results, strict=True)
        ]

    async def section(self, viewer: Principal, owner: UUID, key: str) -> AssembledSection | None:
        for section in await self.visible(viewer, owner):
            if section.key == key:
                result = await self.compute(section, viewer, owner)
                return AssembledSection(section.key, section.owner, section.label_key, section.order, result)
        return None
