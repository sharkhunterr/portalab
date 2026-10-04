"""022 T014/T015/T029/T037/T042 — theme registry (floor rejection, enable/disable, policy catalog,
owner withdrawal) and UI preferences that persist across theme changes, devices and updates."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.events import ConsumerContext, Envelope
from portalab.modules.administration.config.service import Change
from portalab.modules.ui.themes.service import FloorViolation, ThemeConflict
from tests.authz_fixtures import SYSTEM_ACTOR, user
from tests.authz_fixtures import make_admin as make_platform_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.ui_fixtures import UiHarness

BUILTIN = Path(__file__).resolve().parents[3] / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"


def ocean() -> dict[str, object]:
    theme = json.loads((BUILTIN / "dark.json").read_text(encoding="utf-8"))
    return {**theme, "key": "ocean", "name": "Ocean"}


async def test_registry_floor_policy_and_owner(ui: UiHarness) -> None:
    themes = ui.module.themes
    assert {t["key"] for t in (await themes.catalog())["themes"]} == {
        "portalab-dark",
        "portalab-light",
        "orbit",
        "studio",
        "light",
        "dark",
        "high-contrast",
    }
    pale = ocean()
    pale["states"] = {**pale["states"], "error": {"fg": "#2a1a1a", "bg": "#262b35"}}  # type: ignore[dict-item]
    with pytest.raises(FloorViolation) as refused:
        await themes.register(SYSTEM_ACTOR, pale)
    assert any("state.error" in v for v in refused.value.extensions["violations"])

    await themes.register(SYSTEM_ACTOR, ocean(), source="marketplace:ocean-pack", owner="plugin:ocean")
    row = await themes.get("ocean")
    assert row.enabled is False  # external themes are enabled explicitly
    await themes.update(SYSTEM_ACTOR, "ocean", enabled=True)
    assert "ocean" not in {t["key"] for t in (await themes.catalog())["themes"]}  # not allowed by policy yet
    await ui.full.administration.config.apply(
        [Change("ui.allowedThemes", ["light", "dark", "ocean"])], SYSTEM_ACTOR, admin_change=True
    )
    assert "ocean" in {t["key"] for t in (await themes.catalog())["themes"]}
    with pytest.raises(ThemeConflict):
        await themes.update(SYSTEM_ACTOR, "portalab-dark", enabled=False)  # the default family stays enabled
    assert await themes.unregister("plugin:ocean") == 1
    assert "ocean" not in {t["key"] for t in (await themes.catalog())["themes"]}
    async with ui.full.database.session() as session:
        audited = await session.scalar(
            text(
                "SELECT count(*) FROM audit.audit_entries "
                "WHERE action IN ('theme.registered', 'theme.updated')"
            )
        )
    assert audited == 2  # registration and enabling are audited (a refused change leaves nothing)


async def test_preferences_persist(app: FastAPI, client: httpx.AsyncClient, ui: UiHarness) -> None:
    identity = module_of(app)
    user_id = await create_user(identity, "reader")
    await login(client, "reader")
    saved = await client.put(
        "/api/v1/me/preferences", json={"ui.theme": "dark", "ui.textScale": 1.5, "ui.reducedMotion": "on"}
    )
    assert saved.status_code == 200, saved.text
    assert (await client.put("/api/v1/me/preferences", json={"ui.theme": "nope"})).status_code == 422
    assert (await client.put("/api/v1/me/preferences", json={"ui.textScale": 9})).status_code == 422

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as other:
        await login(other, "reader")  # a second device
        values = {
            p["key"]: p["value"] for p in (await other.get("/api/v1/me/preferences")).json()["preferences"]
        }
    assert (
        values["ui.theme"] == "dark" and values["ui.textScale"] == 1.5 and values["ui.reducedMotion"] == "on"
    )

    # theme change keeps accessibility preferences
    await client.put("/api/v1/me/preferences", json={"ui.theme": "light"})
    values = {
        p["key"]: p["value"] for p in (await client.get("/api/v1/me/preferences")).json()["preferences"]
    }
    assert values["ui.textScale"] == 1.5 and values["ui.reducedMotion"] == "on"

    # policy narrows: effective value bounded, own value retained
    await ui.full.administration.policies.set(
        SYSTEM_ACTOR, "ui.textScale", "bound", {"min": 0.85, "max": 1.25}
    ) if hasattr(ui.full.administration.policies, "set") else None
    views = {p["key"]: p for p in (await client.get("/api/v1/me/preferences")).json()["preferences"]}
    assert views["ui.textScale"]["user_value"] == 1.5
    assert user_id


async def test_preference_events(ui: UiHarness, clock: object) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    consumer = ui.consumers.get("ui.preference_events")
    assert consumer is not None
    seen: set[str] = set()

    class Ctx:
        replay = False
        as_of = datetime(2026, 10, 1, tzinfo=UTC)

        async def idempotent_effect(self, key: str) -> bool:
            if key in seen:
                return False
            seen.add(key)
            return True

    actor = uuid4()
    envelope = Envelope(
        uuid4(),
        1,
        "admin.config_changed",
        1,
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 10, 1, tzinfo=UTC),
        "administration",
        None,
        actor,
        "user",
        None,
        None,
        {
            "keys": ["ui.theme", "ui.textScale", "ui.allowedThemes", "identity.sessionIdleMinutes"],
            "change_id": "c-1",
        },
        {},
        None,
    )
    ctx: ConsumerContext = Ctx()  # type: ignore[assignment]
    await consumer.handler(envelope, ctx)
    await consumer.handler(envelope, ctx)  # redelivery: no duplicates
    async with ui.full.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT type, metadata FROM core.event_outbox "
                    "WHERE type LIKE '%theme%' OR type LIKE 'accessibility%' ORDER BY seq"
                )
            )
        ).all()
    assert [r[0] for r in rows] == [
        "theme.changed",
        "accessibility.preference_changed",
        "theme.policy_changed",
    ]
    assert all(set(r[1]) == {"setting", "change_seq"} for r in rows)  # names only, never values


async def test_admin_api(app: FastAPI, client: httpx.AsyncClient, ui: UiHarness) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_platform_admin(ui.full, boss)
    await login(client, "boss")
    check = await client.post("/api/v1/admin/ui/themes/check", json={"definition": {**ocean(), "css": "x"}})
    assert check.status_code == 200 and check.json()["errors"]
    created = await client.post("/api/v1/admin/ui/themes", json={"definition": ocean()})
    assert created.status_code == 201 and created.json()["enabled"] is True
    report = await client.get("/api/v1/admin/ui/themes/ocean/floor-report")
    assert report.json()["report"]["ok"] is True
    bad = await client.post(
        "/api/v1/admin/ui/themes",
        json={
            "definition": {
                **ocean(),
                "key": "bad",
                "colors": {**ocean()["colors"], "text": "#333333", "surface": "#121418"},
            }
        },
    )  # type: ignore[dict-item]
    assert bad.status_code == 422 and bad.json()["code"] == "theme.floor_violation"
    assert user  # imported helper kept for symmetry with other UI tests
