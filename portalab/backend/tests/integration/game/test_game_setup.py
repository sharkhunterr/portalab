"""Issue 253 — the game setup Portalab ships (the LAN's) applied to a fresh portal: its rules published, its
level curve and rewards, achievements, quests and campaigns in place, through the modules' own services; what
the shop does not sell is said, never fatal; a second application changes nothing; the portal's setup then
reads back as the one applied."""

import secrets
from pathlib import Path

import pytest

from portalab.app import game_setup
from portalab.app.wiring import wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.authz_port import Principal
from portalab.core.db import Database

pytestmark = pytest.mark.integration


async def test_the_lan_setup_on_a_fresh_portal(database: Database, tmp_path: Path) -> None:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=new_registry(), secret_key=secrets.token_bytes(32)
    )
    await platform.authz.catalog.sync()
    await platform.refresh_config()
    await platform.gamification.start()
    admin = await platform.identity.bootstrap.create_first_admin(
        login="admin", password=secrets.token_urlsafe(16), display_name="Admin", email=None
    )
    actor = Principal(user_id=admin)
    lan = game_setup.preset("lan")
    assert lan["format"] == game_setup.FORMAT and lan["rules"] and lan["achievements"]

    first = await game_setup.apply(platform, actor, lan)
    fatal = [s for s in first["skipped"] if s["reason"] != "product not in this shop"]
    assert fatal == [], fatal
    assert first["applied"]["rules"] == len(lan["rules"])
    assert first["applied"]["campaigns"] == len(lan["campaigns"])
    assert first["applied"]["curve"] == 1

    now = await game_setup.export(platform)
    assert {r["key"] for r in now["rules"]} == {r["key"] for r in lan["rules"]}
    assert {a["key"] for a in now["achievements"]} >= {a["key"] for a in lan["achievements"]}
    assert {q["key"] for q in now["quests"]} >= {q["key"] for q in lan["quests"]}
    assert {c["key"] for c in now["campaigns"]} == {c["key"] for c in lan["campaigns"]}
    assert now["curve"] == lan["curve"]
    assert now["settings"]["economy.streak"] == lan["settings"]["economy.streak"]

    again = await game_setup.apply(platform, actor, lan)
    assert sum(again["applied"].values()) == 0, again["applied"]


async def test_a_wrong_setup_is_refused(database: Database, tmp_path: Path) -> None:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=new_registry(), secret_key=secrets.token_bytes(32)
    )
    with pytest.raises(ValueError):
        await game_setup.apply(platform, Principal(channel="system"), {"format": "something else"})
    with pytest.raises(KeyError):
        game_setup.preset("../secrets")
