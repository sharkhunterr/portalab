"""027 — one-cell tiles: a shortcut opens a portal page or an https link of the member's choice (anything
else shows nothing), a value tile names what it shows; « since your last visit » is a widget too."""

from datetime import UTC, datetime
from uuid import uuid4

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.modules.dashboard.summary.aggregator import Summary
from portalab.modules.dashboard.widgets.builtin import (
    SHORTCUT,
    VALUE,
    ShortcutProvider,
    SinceLastVisitProvider,
    ValueProvider,
)

ME = Principal(user_id=uuid4())
CTX = LocaleContext()


async def test_shortcut_opens_a_page_or_an_https_link() -> None:
    tile = ShortcutProvider()
    page = await tile.load(ME, {"destination": "requests", "label": " Mes demandes "}, CTX)
    assert page.state == "available" and page.data is not None
    shown = (page.data["route"], page.data["icon"], page.data["label"])
    assert shown == ("/media/requests", "inbox", "Mes demandes")
    link = await tile.load(ME, {"destination": "link", "url": "https://plex.example.org"}, CTX)
    assert link.data is not None and link.data["route"] is None
    assert link.data["href"] == "https://plex.example.org"
    unsafe = await tile.load(ME, {"destination": "link", "url": "javascript:alert(1)"}, CTX)
    assert unsafe.state == "no-data"
    assert SHORTCUT.size.default.w == 1 and SHORTCUT.size.default.h == 1 and SHORTCUT.multiple


async def test_value_tile_keeps_to_known_values() -> None:
    tile = ValueProvider()
    assert (await tile.load(ME, {"metric": "coins"}, CTX)).data == {"metric": "coins"}
    assert (await tile.load(ME, {"metric": "password"}, CTX)).data == {"metric": "level"}
    assert VALUE.size.min.w == 1 and VALUE.size.min.h == 1


async def test_since_last_visit_widget() -> None:
    at = datetime(2026, 10, 6, tzinfo=UTC)

    class _Summary:
        def __init__(self, items: list[ChangeItem]) -> None:
            self.items = items

        async def summary(self, principal: Principal, ctx: LocaleContext) -> Summary:
            return Summary(since=at, items=list(self.items))

    empty = await SinceLastVisitProvider(_Summary([])).load(ME, {}, CTX)
    assert empty.state == "no-data"  # « hide when empty » can take it away
    item = ChangeItem(kind="news", occurred_at=at, ref="/news/a", title="A")
    full = await SinceLastVisitProvider(_Summary([item])).load(ME, {}, CTX)
    assert full.state == "available" and full.data is not None
    assert [i["ref"] for i in full.data["items"]] == ["/news/a"]
