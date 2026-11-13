"""Issue 253 — the game setup Portalab ships (the LAN's) applied to a fresh portal: its rules published, its
level curve and rewards, achievements, quests and campaigns in place, through the modules' own services; what
the shop does not sell is said, never fatal; a second application changes nothing; the portal's setup then
reads back as the one applied. The shop comes with it: Portalab's catalog, the packs switched on or installed
(their products stay theirs), the products the administrators made and the scenes their boosters wear. The
packs are a part of their own: the arrival wizard installs them when the portal opens, a few at a time, and a
level's reward that names one of their products keeps it in the meantime."""

import secrets
import shutil
from pathlib import Path
from typing import Any

import pytest

from portalab.app import game_setup
from portalab.app.demo_shop import SHOP
from portalab.app.wiring import wire_platform
from portalab.capabilities.catalog import new_registry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.visuals.builtin import BuiltinSync

REPOSITORY = Path(__file__).resolve().parents[4]
pytestmark = pytest.mark.integration


async def _portal(database: Database, tmp_path: Path) -> tuple[Any, Principal]:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=new_registry(), secret_key=secrets.token_bytes(32)
    )
    await platform.authz.catalog.sync()
    await platform.refresh_config()
    await platform.gamification.start()
    admin = await platform.identity.bootstrap.create_first_admin(
        login="admin", password=secrets.token_urlsafe(16), display_name="Admin", email=None
    )
    return platform, Principal(user_id=admin)


async def test_the_lan_setup_on_a_fresh_portal(database: Database, tmp_path: Path) -> None:
    platform, actor = await _portal(database, tmp_path)
    lan = game_setup.preset("lan")
    assert lan["format"] == game_setup.FORMAT and lan["rules"] and lan["achievements"]
    assert lan["shop"]["catalog"] and lan["shop"]["packs"] and lan["shop"]["products"]
    play = tuple(p for p in game_setup.PARTS if p not in ("shop", "packs"))  # their own test, fewer packs

    first = await game_setup.apply(platform, actor, lan, play)
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

    again = await game_setup.apply(platform, actor, lan, play)
    assert sum(again["applied"].values()) == 0, again["applied"]


async def test_the_shop_comes_with_the_recommended_install(
    database: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform, actor = await _portal(database, tmp_path)
    builtin = tmp_path / "builtin"
    for pack in ("portalab-socle", "portalab-academy"):
        shutil.copytree(REPOSITORY / "packs" / "builtin" / pack, builtin / pack)
    await BuiltinSync(platform.visuals.packs, builtin).run(actor)  # a fresh portal: the socle only on
    examples = tmp_path / "examples"
    shutil.copytree(REPOSITORY / "examples" / "visual-packs" / "mediacards", examples / "mediacards")
    monkeypatch.setenv("PORTALAB_EXAMPLE_PACKS_DIR", str(examples))
    booster = {
        "key": "cards_genre_sf",
        "type": "card_booster",
        "price": 30,
        "rarity": "common",
        "names": {"en": "Science fiction booster", "fr": "Booster Science-fiction"},
        "descriptions": {"fr": "3 cartes tirées parmi les films et séries « Science-fiction »."},
        "payload": {"family": "sf", "cards": 3},
        "collection": "boosters",
        "icon": "layers",
        "repeatable": True,
    }
    scenes = {"card_booster": {"pack": "mediacards", "look": "mediacards"}}
    shop = {
        "catalog": True,
        "packs": ["mediacards", "nowhere", "portalab-academy"],
        "products": [booster],
        "scenes": scenes,
    }
    setup = {"format": game_setup.FORMAT, "version": game_setup.VERSION, "shop": shop}

    # the game step: the shop, the packs left for the opening; a level's reward of a pack's product kept
    academy = min(await platform.visuals.packs.product_keys())
    setup["settings"] = {"economy.levelRewards": [{"level": 5, "coins": 10, "xp": 0, "product": academy}]}
    game = await game_setup.apply(platform, actor, setup, ("shop", "settings"))
    assert game["skipped"] == [] and game["applied"]["packs"] == 0
    assert platform.gamification.config.level_rewards[0]["product"] == academy
    states = {p["id"]: p["state"] for p in await platform.visuals.packs.listing()}
    assert states["portalab-academy"] == "disabled"

    # the opening: the packs a few at a time, each one's scene with it
    first = await game_setup.apply(platform, actor, setup, ("packs",), ["nowhere", "portalab-academy"])
    assert first["skipped"] == [{"part": "packs", "key": "pack nowhere", "reason": "pack not shipped"}]
    assert first["applied"]["packs"] == 1  # academy switched on; mediacards and its scene not yet
    second = await game_setup.apply(platform, actor, setup, ("packs",), ["mediacards"])
    assert second["skipped"] == [] and second["applied"]["packs"] == 2  # installed, then its scene
    catalog = platform.marketplace.catalog
    sold = {p.key: p for p, _ in await catalog.listing(states=("available", "unavailable"))}
    assert {p["key"] for p in SHOP} <= set(sold)  # Portalab's own catalog
    assert sold["cards_genre_sf"].state == "available"  # the administrators' own product
    packs = {p["id"]: p for p in await platform.visuals.packs.listing()}
    assert packs["portalab-academy"]["state"] == "enabled"  # switched on: its products are its own
    assert packs["mediacards"]["state"] == "enabled" and not packs["mediacards"]["builtin"]  # an extension
    assert packs["mediacards"]["source"] == {"kind": "example", "path": "mediacards"}
    assert set(await platform.visuals.packs.product_keys()) <= set(sold)

    # the portal's shop reads back as the one applied: packs named, never their products
    exported = (await game_setup.export(platform))["shop"]
    assert exported["catalog"] and exported["packs"] == ["mediacards", "portalab-academy"]
    assert [p["key"] for p in exported["products"]] == ["cards_genre_sf"]
    assert exported["scenes"] == scenes

    again = await game_setup.apply(platform, actor, setup)
    assert sum(again["applied"].values()) == 0, again["applied"]


async def test_a_wrong_setup_is_refused(database: Database, tmp_path: Path) -> None:
    platform = wire_platform(
        database, data_dir=tmp_path / "data", capabilities=new_registry(), secret_key=secrets.token_bytes(32)
    )
    with pytest.raises(ValueError):
        await game_setup.apply(platform, Principal(channel="system"), {"format": "something else"})
    with pytest.raises(KeyError):
        game_setup.preset("../secrets")
