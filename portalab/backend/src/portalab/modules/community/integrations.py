"""Integrations (T015): the dashboard widget ``community.activity`` (009) — the latest feed entries the
viewer may see, under the same read-time visibility as the feed itself."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.community.feed.service import FeedService
from portalab.modules.community.permissions import READ

OWNER = "module:community"

ACTIVITY_WIDGET = WidgetDefinition(
    key="community.activity",
    owner=OWNER,
    title_key="community:widget.activity.title",
    description_key="community:widget.activity.description",
    icon="users",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 2), max=Size(8, 6)),
    refresh=Refresh(mode="interval", interval_s=300),
    stale_after_s=900,
    component_id="community.activity",
)


class ActivityWidget:
    def __init__(self, feed: FeedService, clock: Clock | None = None) -> None:
        self.feed = feed
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        items, _ = await self.feed.page(principal, limit=5)
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "items": [
                    {
                        "id": str(i.id),
                        "actor_id": str(i.actor_id),
                        "actor_name": i.actor_name,
                        "text_key": i.text_key,
                        "params": i.params,
                        "occurred_at": i.occurred_at.isoformat(),
                    }
                    for i in items
                ]
            },
        )
