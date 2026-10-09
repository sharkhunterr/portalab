"""027 (#31) — the widgets' other looks: ``style`` is a setting whose default is the original look
(« classic », free); every look sold in the shop is one its widget accepts, and every look a widget offers
is on sale."""

from portalab.app.demo_shop import SHOP
from portalab.capabilities.dashboard import WidgetDefinition, with_styles
from portalab.modules.calendar.module import UPCOMING
from portalab.modules.community.integrations import ACTIVITY_WIDGET
from portalab.modules.dashboard.widgets.builtin import CLOCK, COUNTDOWN, SERVICES_SUMMARY
from portalab.modules.gamification.integrations import DAILY_WIDGET, PROGRESS_WIDGET
from portalab.modules.media.providers.insight_widgets import (
    POSTER_WALL,
    RECENT_RELEASES,
    RECENTLY_ADDED,
    RECENTLY_REQUESTED,
    STATS,
)
from portalab.modules.media.providers.widgets import CONTINUE
from portalab.modules.news.integrations import LATEST
from tests.unit.dashboard.fakes import definition

STYLED: tuple[WidgetDefinition, ...] = (
    UPCOMING,
    ACTIVITY_WIDGET,
    CLOCK,
    COUNTDOWN,
    SERVICES_SUMMARY,
    DAILY_WIDGET,
    PROGRESS_WIDGET,
    POSTER_WALL,
    RECENT_RELEASES,
    RECENTLY_ADDED,
    RECENTLY_REQUESTED,
    STATS,
    CONTINUE,
    LATEST,
)


def _styles(widget: WidgetDefinition) -> list[str]:
    return list(widget.config_schema["properties"]["style"]["enum"])


def test_a_style_setting_defaults_to_the_original_look() -> None:
    styled = with_styles(definition("t.w"), "neon", "paper")
    assert _styles(styled) == ["classic", "neon", "paper"]
    assert styled.config_defaults["style"] == "classic"
    assert definition("t.w").config_defaults.get("style") is None  # the original definition is untouched


def test_every_look_on_sale_is_one_its_widget_offers_and_back() -> None:
    offered = {(w.key, style) for w in STYLED for style in _styles(w) if style != "classic"}
    on_sale = set()
    for product in SHOP:
        if product["type"] == "widget_option" and ":style=" in product["payload"]["option"]:
            key, style = product["payload"]["option"].split(":style=")
            on_sale.add((key, style))
    assert on_sale == offered
    assert all(w.config_defaults["style"] == "classic" for w in STYLED)
