"""Discovery shelves (T012; US8): built-in lists for a viewer — ``new_members``, ``recent_unlocks`` and
``activity_highlights`` — each bound by the same visibility as its source surface (directory listing,
feed). An empty shelf offers a next action. Projects needing votes or help join in slice D."""

from collections.abc import Mapping, Sequence
from typing import Any

from portalab.capabilities.community import DiscoveryShelf, ShelfRegistry
from portalab.core.authz_port import Principal
from portalab.modules.community.feed.service import FeedItem, FeedService
from portalab.modules.community.members.service import Members

OWNER = "module:community"
UNLOCKS = ("achievement.unlocked",)


def _entry(item: FeedItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "actor_id": str(item.actor_id),
        "actor_name": item.actor_name,
        "text_key": item.text_key,
        "params": item.params,
        "url": f"/community/members/{item.actor_id}",
        "occurred_at": item.occurred_at.isoformat(),
    }


def register_builtin_shelves(registry: ShelfRegistry, members: Members, feed: FeedService) -> None:
    async def new_members(viewer: Principal, limit: int) -> Sequence[Mapping[str, Any]]:
        page = await members.page(viewer, limit=limit, newest=True)
        return [
            {
                "id": str(m.id),
                "display_name": m.display_name,
                "url": f"/community/members/{m.id}",
                "joined_at": m.joined_at.isoformat(),
            }
            for m in page.items
        ]

    async def recent_unlocks(viewer: Principal, limit: int) -> Sequence[Mapping[str, Any]]:
        items, _ = await feed.page(viewer, limit=limit, kinds=UNLOCKS)
        return [_entry(i) for i in items]

    async def highlights(viewer: Principal, limit: int) -> Sequence[Mapping[str, Any]]:
        items, _ = await feed.page(viewer, limit=limit, exclude=UNLOCKS)
        return [_entry(i) for i in items]

    for key, provider, order, action in (
        ("new_members", new_members, 10, "/community/members"),
        ("recent_unlocks", recent_unlocks, 20, "/progression"),
        ("activity_highlights", highlights, 30, "/community/feed"),
    ):
        if registry.get(key) is None:
            registry.register(
                DiscoveryShelf(key, OWNER, provider, order, f"community:discovery.{key}", action)
            )
