"""Issue 159 — the site's identity: the administrators name the site and its currency, give it a slogan, a
logo and an icon; the sign-in page reads them without a session; the catalogs (the pages, the e-mails) speak
the site's words; « restore » brings Portalab's own back; every change is audited."""

import io

import httpx
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import text

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.catalog.service import CatalogService
from tests.authz_fixtures import make_admin as make_platform_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.ui_fixtures import UiHarness


def png(width: int, height: int) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (width, height), (200, 40, 90, 255)).save(output, format="PNG")
    return output.getvalue()


async def test_the_site_is_named_and_its_currency_too(
    app: FastAPI, client: httpx.AsyncClient, ui: UiHarness
) -> None:
    public = (await client.get("/api/v1/auth/site")).json()  # no session: the sign-in page asks it
    assert public["name"] == "Portalab" and public["custom"] is False and public["logo"] is None

    boss = await create_user(module_of(app), "boss")
    await create_user(module_of(app), "member")
    await make_platform_admin(ui.full, boss)
    await login(client, "member")
    assert (await client.get("/api/v1/admin/site")).status_code == 403
    await login(client, "boss")

    refused = await client.put("/api/v1/admin/site", json={"name": "Xeno{portal}"})
    assert refused.status_code == 422 and refused.json()["code"] == "ui.site_identity_invalid"
    saved = await client.put(
        "/api/v1/admin/site",
        json={
            "name": "  Xenoportal ",
            "short_name": "XP",
            "tagline": {"fr": "Vos services, votre communauté.", "en": ""},
            "currency": {
                "en": {"one": "Xenocoin", "other": "Xenocoins"},
                "fr": {"one": "Xénocoin", "other": "Xénocoins"},
            },
            "currency_short": "XC",
            "currency_icon": "gem",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (
        body["name"] == "Xenoportal"
        and body["short_name"] == "XP"
        and body["tagline"] == {"fr": "Vos services, votre communauté."}
    )
    assert (
        body["currency"]["fr"] == {"one": "Xénocoin", "other": "Xénocoins"} and body["currency_short"] == "XC"
    )

    logo = await client.put(
        "/api/v1/admin/site/logo", content=png(900, 300), headers={"content-type": "image/png"}
    )
    assert logo.status_code == 200 and logo.json()["logo"].startswith("/api/v1/auth/site/logo?v=")
    icon = await client.put(
        "/api/v1/admin/site/icon", content=png(64, 40), headers={"content-type": "image/png"}
    )
    assert icon.status_code == 200
    broken = await client.put("/api/v1/admin/site/icon", content=b"not an image")
    assert broken.status_code == 422 and broken.json()["code"] == "ui.site_identity_invalid"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as anyone:
        seen = (await anyone.get("/api/v1/auth/site")).json()
        assert seen["name"] == "Xenoportal" and seen["custom"] and seen["currency_icon"] == "gem"
        image = await anyone.get("/api/v1/auth/site/icon")
        assert image.status_code == 200 and image.headers["content-type"] == "image/png"
        with Image.open(io.BytesIO(image.content)) as square:
            assert square.size == (512, 512)  # a home-screen icon is square
        with Image.open(io.BytesIO((await anyone.get("/api/v1/auth/site/logo")).content)) as wide:
            assert max(wide.size) == 512
        manifest = (await anyone.get("/api/v1/auth/site/manifest")).json()
        assert manifest["name"] == "Xenoportal" and manifest["short_name"] == "XP" and manifest["icons"]
        assert (await anyone.get("/api/v1/admin/site")).status_code == 401

    catalogs = CatalogService(ui.full.database, terms=lambda: ui.module.site)
    french = LocaleContext(language="fr", locale="fr")
    english = LocaleContext()
    assert (
        catalogs.t("buy.confirmText", french, {"price": 1}, namespace="marketplace")
        == "Dépenser 1 Xénocoin ?"
    )
    assert (
        catalogs.t("buy.confirmText", english, {"price": 3}, namespace="marketplace") == "Spend 3 Xenocoins?"
    )
    assert (
        catalogs.t("verification.subject", english, namespace="notifications")
        == "Confirm your Xenoportal account"
    )
    assert catalogs.t("visuals.builtin", english, namespace="admin") == "Portalab"  # the software's name
    messages, version = catalogs.bundle("gamification", french)
    assert messages["value.coins"] == "Xénocoins"

    reset = (await client.delete("/api/v1/admin/site")).json()
    assert reset["name"] is None and reset["logo"] is None and reset["currency"] == {}
    assert catalogs.t("buy.confirmText", english, {"price": 3}, namespace="marketplace") == "Spend 3 Coins?"
    assert catalogs.bundle("gamification", french)[1] != version
    assert (await client.get("/api/v1/auth/site/logo")).status_code == 404

    async with ui.full.database.session() as session:
        actions = (
            await session.scalars(
                text(
                    "SELECT action FROM audit.audit_entries "
                    "WHERE action LIKE 'ui.site_identity.%' ORDER BY occurred_at"
                )
            )
        ).all()
    assert actions == [
        "ui.site_identity.updated",
        "ui.site_identity.logo_set",
        "ui.site_identity.icon_set",
        "ui.site_identity.reset",
    ]
