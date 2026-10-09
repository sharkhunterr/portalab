"""Dashboard widget ``campaigns.active`` (009): the campaigns active now for the viewer."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.permissions import READ
from portalab.modules.campaigns.presentation.service import Presentation

OWNER = "module:campaigns"
ACTIVE_WIDGET = WidgetDefinition(
    key="campaigns.active",
    owner=OWNER,
    title_key="campaigns:widget.active.title",
    description_key="campaigns:widget.active.description",
    icon="sparkles",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(12, 4)),
    refresh=Refresh(mode="event", events=("campaign.started", "campaign.ended")),
    stale_after_s=600,
    component_id="campaigns.active",  # 027: a card per campaign — countdown and boosts
)


class ActiveWidget:
    def __init__(self, presentation: Presentation, clock: Clock | None = None) -> None:
        self.presentation = presentation
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        active = await self.presentation.active_for_user(user)
        if not active:
            # 027: nothing running — say what is coming next (a pinned block is never empty)
            now = utc_now(self.clock)
            upcoming = await self.presentation.items(now, now + timedelta(days=120), principal, ctx)
            nxt = next(
                (i for i in upcoming.items if i.starts_at and i.starts_at > now and i.status != "cancelled"),
                None,
            )
            return WidgetPayload(
                "available",
                as_of=now,
                data={
                    "items": [],
                    "next": {
                        "title": nxt.title,
                        "starts_at": nxt.starts_at.isoformat() if nxt.starts_at else None,
                        "route": nxt.url_ref,
                    }
                    if nxt
                    else None,
                },
            )
        items = []
        for c in active:
            view = await self.presentation.public_view(c.key)
            window = (view or {}).get("window")
            items.append(
                {
                    "key": c.key,
                    "title": c.name,
                    "route": f"/campaigns/{c.key}",
                    # 027: the running window — how long is left and how far through it we are
                    "starts_at": window["start_at"] if window else c.started_at.isoformat(),
                    "ends_at": window["end_at"] if window else c.ends_at.isoformat() if c.ends_at else None,
                    "description": (view or {}).get("description") or "",
                    "boosts": (view or {}).get("modifiers") or [],
                }
            )
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})
