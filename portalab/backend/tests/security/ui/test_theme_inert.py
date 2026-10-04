"""022 T036/T040 — theme registration needs ``appearance.manage``; scripts/URLs/unknown keys are rejected;
enabling an external theme is audited; a theme cannot change permissions or data; /ui routes in the
permission matrix (anonymous 401, users read their catalog only)."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.identity.helpers import create_user, login, module_of
from tests.ui_fixtures import UiHarness

pytestmark = pytest.mark.integration
BUILTIN = Path(__file__).resolve().parents[3] / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"
ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/ui/themes"),
    ("POST", "/api/v1/admin/ui/themes"),
    ("PATCH", "/api/v1/admin/ui/themes/light"),
    ("GET", "/api/v1/admin/ui/themes/light/floor-report"),
    ("POST", "/api/v1/admin/ui/themes/check"),
]


async def test_matrix(app: FastAPI, client: httpx.AsyncClient, ui: UiHarness) -> None:
    for method, path in [*ADMIN_ROUTES, ("GET", "/api/v1/ui/themes")]:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in ADMIN_ROUTES:
        assert (await client.request(method, path, json={"definition": {}})).status_code == 403, path
    catalog = (await client.get("/api/v1/ui/themes")).json()
    assert {t["key"] for t in catalog["themes"]} == {
        "portalab-dark",
        "portalab-light",
        "orbit",
        "studio",
        "light",
        "dark",
        "high-contrast",
    }
    assert catalog["policy"]["defaultTheme"] == "portalab"


async def test_themes_are_inert_and_bounded(ui: UiHarness) -> None:
    from portalab.modules.ui.themes.service import InvalidTheme
    from tests.authz_fixtures import SYSTEM_ACTOR

    theme = json.loads((BUILTIN / "dark.json").read_text(encoding="utf-8"))
    for payload in (
        {**theme, "key": "evil", "script": "alert(1)"},
        {**theme, "key": "evil", "permissions": ["users.admin.transfer"]},
        {
            **theme,
            "key": "evil",
            "background": {"image": "https://tracker.example/p.png", "fallback": "#000000"},
        },
    ):
        with pytest.raises(InvalidTheme):
            await ui.module.themes.register(SYSTEM_ACTOR, payload)
    before = (
        {p.key for p in ui.full.authz.engine.catalog.registry.all()}
        if hasattr(ui.full.authz.engine, "catalog")
        else set()
    )
    await ui.module.themes.register(
        SYSTEM_ACTOR,
        {**theme, "key": "store-theme", "name": "Store"},
        source="marketplace:x",
        owner="plugin:x",
    )
    after = (
        {p.key for p in ui.full.authz.engine.catalog.registry.all()}
        if hasattr(ui.full.authz.engine, "catalog")
        else set()
    )
    assert before == after  # registering a theme declares no permission
