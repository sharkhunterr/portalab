"""023 T017 — conformance sweep: after disable and after quarantine, every registry holds zero
contributions of the plugin (nav, pages, widgets, actions, search, calendar, statistics, automations, AI
tools, categories, themes, i18n, permissions, settings, events, capabilities, products, media types,
profile sections, shelves, connectors, routes); plugin data untouched; re-enabling restores them."""

import pytest
from sqlalchemy import text

from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration


async def count_owned(pl: PlHarness) -> int:
    return len([e for e in await pl.module.ledger.entries("hello") if e.state == "active"])


async def test_sweep_after_disable_quarantine_and_reenable(pl: PlHarness) -> None:
    await pl.installed(pl.hello())
    greet = pl.registries.routes.get("hello", "POST", "greet")
    assert greet is not None
    await greet.handler(SYSTEM, {}, {"name": "Ada"})
    active = await count_owned(pl)
    assert active >= 23

    await pl.module.lifecycle.disable(SYSTEM, "hello")
    assert await pl.registries.leftovers("plugin:hello") == {}
    assert not pl.themes.themes["hello-dusk"]["enabled"]
    assert (
        pl.registries.pages.of("hello") == [] and pl.registries.routes.get("hello", "POST", "greet") is None
    )

    await pl.module.lifecycle.enable(SYSTEM, "hello")
    await pl.module.lifecycle.load_enabled()
    assert await count_owned(pl) == active  # restored
    assert pl.themes.themes["hello-dusk"]["enabled"] and pl.registries.pages.get("hello", "main") is not None

    await pl.module.lifecycle.quarantine("hello", "test")
    assert await pl.registries.leftovers("plugin:hello") == {}
    async with pl.database.session() as session:
        kept = await session.scalar(text("SELECT count(*) FROM plugin_hello.greetings"))
        state = await session.scalar(text("SELECT state FROM plugins.plugins WHERE key = 'hello'"))
    assert kept == 1 and state == "quarantined"  # data never deleted by disable/quarantine
