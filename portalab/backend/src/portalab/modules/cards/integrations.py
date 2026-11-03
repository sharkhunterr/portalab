"""#347: the dashboard widget ``cards.collection`` — « My Mediacards »: where the member's collection stands
and the boosters waiting to be opened; nothing for a member who does not collect the cards (issue 243)."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.packs import Packs
from portalab.modules.cards.permissions import READ
from portalab.modules.cards.service import CardService

OWNER = "module:cards"

COLLECTION_WIDGET = WidgetDefinition(
    key="cards.collection",
    owner=OWNER,
    title_key="gamification:cards.widget.title",
    description_key="gamification:cards.widget.description",
    icon="layers",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(8, 5)),
    refresh=Refresh(mode="interval", interval_s=900),
    stale_after_s=1800,
    component_id="cards.collection",
)
COLLECTION_PACKS = 12  # the sealed packs drawn (stacked when identical); the count says the rest


class CollectionWidget:
    """#347: the collection's summary as on ``/cards`` (the cards held of all there are, the sets started,
    the copies) and the packs to open, sealed as on the boosters' view."""

    def __init__(self, service: CardService, packs: Packs, clock: Clock | None = None) -> None:
        self.service = service
        self.packs = packs
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None or not await self.packs.collects(user):
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        summary = await self.service.summary(user)
        if not summary["cards"] and not summary["unopened"]:  # no card made yet: nothing to collect
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        packs: list[dict[str, Any]] = []
        if summary["unopened"]:  # sealed: their cards stay hidden
            packs = await self.service.packs(user, unopened=True, limit=COLLECTION_PACKS)
        return WidgetPayload("available", as_of=utc_now(self.clock), data={**summary, "packs": packs})
