"""Built-in profile sections (T007): ``identity`` (002, datum ``member_listing``), ``progression`` and
``achievements`` (013 ``ProgressionReader``, datum ``progression``), ``activity`` (the member's feed
entries, datum ``community_activity``) and ``projects`` (datum ``projects``; empty until slice D)."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from portalab.capabilities.community import ProfileSection, SectionRegistry, SectionResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import PROGRESSION
from portalab.core.authz_port import Principal
from portalab.modules.community.feed.service import FeedService
from portalab.modules.community.preferences import ACTIVITY, MEMBER_LISTING, PROJECTS

OWNER = "module:community"
PROGRESSION_DATUM = "progression"  # owned by gamification (013)


def _progression(capabilities: CapabilityRegistry) -> Any | None:
    providers = capabilities.system_providers(PROGRESSION)
    return providers[0].provider if providers else None


def register_builtin_sections(
    registry: SectionRegistry,
    capabilities: CapabilityRegistry,
    feed: FeedService,
    names: Callable[[UUID], Awaitable[str | None]],
) -> None:
    async def identity(owner: UUID, viewer: Principal) -> SectionResult:
        name = await names(owner)
        if name is None:
            return SectionResult("no-data")
        return SectionResult("available", {"display_name": name})

    async def progression(owner: UUID, viewer: Principal) -> SectionResult:
        reader = _progression(capabilities)
        if reader is None:
            return SectionResult("unavailable")
        progress = getattr(reader, "progress", None)
        if progress is None:
            return SectionResult("available", {"level": await reader.level(owner)})
        value = await progress(owner)
        return SectionResult(
            "available",
            {
                "level": value.level,
                "xp": value.xp,
                "next_level_at": value.next_level_at,
                "contribution": value.contribution,
                "achievements": value.achievements,
            },
        )

    async def achievements(owner: UUID, viewer: Principal) -> SectionResult:
        reader = _progression(capabilities)
        listing = getattr(reader, "achievement_list", None) if reader is not None else None
        if listing is None:
            return SectionResult("unavailable")
        items = await listing(owner, 12)
        return SectionResult("available" if items else "no-data", {"items": items})

    async def activity(owner: UUID, viewer: Principal) -> SectionResult:
        entries, _ = await feed.page(viewer, actor=owner, limit=10)
        return SectionResult(
            "available" if entries else "no-data",
            {
                "items": [
                    {
                        "id": str(e.id),
                        "kind": e.kind,
                        "text_key": e.text_key,
                        "params": e.params,
                        "occurred_at": e.occurred_at.isoformat(),
                    }
                    for e in entries
                ]
            },
        )

    async def projects(owner: UUID, viewer: Principal) -> SectionResult:
        return SectionResult("no-data", {"items": []})  # proposals arrive with slice D (015)

    for key, datum, provider, order in (
        ("identity", MEMBER_LISTING, identity, 10),
        ("progression", PROGRESSION_DATUM, progression, 20),
        ("achievements", PROGRESSION_DATUM, achievements, 30),
        ("activity", ACTIVITY, activity, 40),
        ("projects", PROJECTS, projects, 50),
    ):
        if registry.get(key) is None:
            registry.register(
                ProfileSection(key, OWNER, datum, provider, order, label_key=f"community:section.{key}")
            )
