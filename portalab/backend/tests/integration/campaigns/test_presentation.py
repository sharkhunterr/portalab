"""014 T023 — presentation: the campaign theme overlay per user (audience-filtered, priority order), only
themes the 022 policy allows, the user's ``ui.campaignThemes = ignore`` respected; presentation never
changes permissions or state."""

import pytest
from httpx import AsyncClient

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.themes import CAPABILITY as THEMES
from portalab.modules.ui import settings as _ui_settings  # noqa: F401 — declares ui.campaignThemes
from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness, later, paris
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class Catalog:
    def __init__(self) -> None:
        self.allowed = {"pumpkin", "ghost"}

    async def allowed_keys(self) -> frozenset[str]:
        return frozenset(self.allowed)


async def test_theme_overlay(cm: CampHarness, client: AsyncClient) -> None:
    catalog = Catalog()
    cm.ev.full.identity.capabilities.provide(THEMES, catalog, instance_ref="t", owner="module:ui")
    ursula = cm.people["ursula"]
    await cm.create(definition={**HALLOWEEN, "theme": {"theme_key": "pumpkin", "presentation_priority": 10}})
    await cm.create(
        "vip_night",
        {
            **HALLOWEEN,
            "names": {"en": "VIP night"},
            "theme": {"theme_key": "ghost", "presentation_priority": 50},
            "modifiers": [
                {
                    "id": "vip",
                    "value": "xp",
                    "factor": 2,
                    "when": {"audience": {"kind": "users", "users": [str(ursula)]}},
                }
            ],
        },
    )
    await cm.at(later(paris(10, 20, 0), minutes=1))
    await login(client, "ursula")
    shown = (await client.get("/api/v1/campaigns/active/presentation")).json()
    assert {c["key"] for c in shown["campaigns"]} == {"halloween", "vip_night"}
    assert shown["theme"] == {"campaign": "vip_night", "theme_key": "ghost"}
    await login(client, "ulrich")
    other = (await client.get("/api/v1/campaigns/active/presentation")).json()
    assert [c["key"] for c in other["campaigns"]] == ["halloween"] and other["theme"][
        "theme_key"
    ] == "pumpkin"
    catalog.allowed = {"ghost"}  # the admin policy no longer allows "pumpkin"
    assert (await client.get("/api/v1/campaigns/active/presentation")).json()["theme"] is None
    writer = cm.ev.full.identity.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)[0].provider
    from portalab.core.authz_port import Principal

    await writer.set_user(Principal(user_id=ursula), "ui.campaignThemes", "ignore")
    await login(client, "ursula")
    opted_out = (await client.get("/api/v1/campaigns/active/presentation")).json()
    assert opted_out["theme"] is None and len(opted_out["campaigns"]) == 2
    assert (await client.get("/api/v1/admin/campaigns")).status_code == 403  # presentation grants nothing
