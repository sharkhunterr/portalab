"""012 T030 — the profile-section and discovery-shelf registries are owner-tagged: ``unregister(owner)``
removes every contribution of that owner (023 conformance sweep, F20) and a key cannot be taken over."""

import pytest

from portalab.capabilities.community import (
    DiscoveryShelf,
    ProfileSection,
    SectionRegistry,
    SectionResult,
    ShelfRegistry,
)


async def section(owner: object, viewer: object) -> SectionResult:
    return SectionResult("available")


async def shelf(viewer: object, limit: int) -> list[dict[str, str]]:
    return []


def test_unregister_removes_every_contribution_of_an_owner() -> None:
    sections, shelves = SectionRegistry(), ShelfRegistry()
    sections.register(ProfileSection("identity", "module:community", "member_listing", section, 10))
    sections.register(ProfileSection("plugin:x.badges", "plugin:x", "progression", section, 60))
    sections.register(ProfileSection("plugin:x.stats", "plugin:x", "progression", section, 70))
    shelves.register(DiscoveryShelf("plugin:x.picks", "plugin:x", shelf))
    with pytest.raises(ValueError, match="already registered"):
        sections.register(ProfileSection("identity", "plugin:x", "member_listing", section))
    assert [s.key for s in sections.all()] == ["identity", "plugin:x.badges", "plugin:x.stats"]
    assert sections.unregister("plugin:x") == 2 and shelves.unregister("plugin:x") == 1
    assert [s.key for s in sections.all()] == ["identity"] and shelves.all() == []
