"""Dashboard bridge (T021): the ``statistics.card`` widget (009) shows any permitted statistic through the
same ``StatisticsProvider`` the API uses — identical values everywhere."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import (
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetUnauthorized,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.statistics import Period
from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden, NotFound
from portalab.modules.statistics.provider.provider import Provider

CARD = WidgetDefinition(
    key="statistics.card",
    owner="module:statistics",
    title_key="statistics:widget.card.title",
    description_key="statistics:widget.card.description",
    icon="chart",
    required_permission="statistics.read",
    config_schema={
        "type": "object",
        "properties": {
            "stat_key": {"type": "string", "pattern": r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", "maxLength": 96},
            "days": {"type": "integer", "minimum": 1, "maximum": 366},
        },
        "additionalProperties": False,
    },
    config_defaults={"stat_key": "users.active_by_day", "days": 30},
    size=SizeLimits(default=Size(4, 2), min=Size(3, 2), max=Size(12, 6)),
    multiple=True,
    stale_after_s=900,
    template="chart",
)

_STATE = {
    "available": "available",
    "partial": "partial",
    "stale": "stale",
    "unavailable": "unavailable",
    "insufficient_data": "no-data",
    "no_data": "no-data",
}


class StatisticCard:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        try:
            result = await self.provider.get(
                str(config.get("stat_key")),
                viewer=principal,
                period=Period("last_n_days", days=int(config.get("days", 30))),
            )
        except (Forbidden, NotFound) as exc:
            raise WidgetUnauthorized() from exc
        if result.state == "locked":
            return WidgetPayload("no-data", data={"locked": True, "hint": result.unlock_hint})
        data = {
            "label": result.key,
            "value": result.value,
            "series": [{"label": result.key, "points": [[p["day"], p["value"]] for p in result.series]}],
            "trend": None
            if result.trend is None
            else {"delta": result.trend.delta, "direction": result.trend.direction},
        }
        return WidgetPayload(_STATE.get(result.state, "available"), as_of=result.as_of, data=data)  # type: ignore[arg-type]
