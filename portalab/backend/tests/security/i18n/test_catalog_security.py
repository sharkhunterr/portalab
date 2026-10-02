"""026 T041/T042 — /i18n routes require authentication, admin routes i18n.manage; catalogs and stats hold
no secrets; content of an unregistered kind (or unreadable item) is indistinguishable from missing."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.modules.i18n.catalog.service import LOCALES_DIR
from portalab.modules.i18n.content.localizer import ContentKind
from tests.authz_fixtures import make_admin
from tests.integration.i18n.conftest import I18nHarness
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


async def test_matrix_and_api(app: FastAPI, client: httpx.AsyncClient, i18n: I18nHarness) -> None:
    for method, path in (
        ("GET", "/api/v1/i18n/context"),
        ("GET", "/api/v1/i18n/languages"),
        ("GET", "/api/v1/i18n/catalogs/core"),
        ("GET", "/api/v1/admin/i18n/catalog-entries"),
        ("PUT", "/api/v1/admin/i18n/catalog-entries"),
        ("GET", "/api/v1/admin/i18n/health"),
    ):
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in (
        ("GET", "/api/v1/admin/i18n/catalog-entries"),
        ("PUT", "/api/v1/admin/i18n/catalog-entries"),
        ("GET", "/api/v1/admin/i18n/health"),
    ):
        assert (await client.request(method, path, json={})).status_code == 403, path
    ctx = (await client.get("/api/v1/i18n/context")).json()
    assert ctx["language"] == "en" and ctx["time_zone"] == "UTC"
    languages = (await client.get("/api/v1/i18n/languages")).json()
    assert [lang["code"] for lang in languages["items"]] == ["en", "fr"]
    catalog = await client.get("/api/v1/i18n/catalogs/shell", params={"lang": "fr"})
    assert catalog.json()["messages"]["signOut"] == "Se déconnecter"
    again = await client.get(
        "/api/v1/i18n/catalogs/shell",
        params={"lang": "fr"},
        headers={"If-None-Match": catalog.headers["ETag"]},
    )
    assert again.status_code == 304
    i18n.module.content_kinds.register(ContentKind("news", "audit.read", "module:news"))
    await i18n.module.content.register_version("news", "n1", "en", state="source", source_language="en")
    hidden = await client.get("/api/v1/i18n/content/news/n1")
    unknown = await client.get("/api/v1/i18n/content/wiki/x")
    assert (
        hidden.status_code == unknown.status_code == 404 and hidden.json()["code"] == unknown.json()["code"]
    )


async def test_admin_health(app: FastAPI, client: httpx.AsyncClient, i18n: I18nHarness) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_admin(i18n.full, boss)
    await login(client, "boss")
    from portalab.capabilities.i18n import LocaleContext

    i18n.module.catalogs.t("missing.key", LocaleContext(language="fr"))
    health = (await client.get("/api/v1/admin/i18n/health")).json()
    assert health["missing"][0]["key"] == "missing.key" and health["missing_by_language"]["fr"] == 1
    bad = await client.put(
        "/api/v1/admin/i18n/catalog-entries",
        json={"namespace": "core", "key": "retry", "language": "fr", "message": "{oops"},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "i18n.invalid_message"


def test_catalog_files_hold_no_secrets() -> None:
    from portalab.core.logging import is_secret_key

    for path in Path(LOCALES_DIR).glob("*/*.json"):
        messages = json.loads(path.read_text(encoding="utf-8"))
        assert not [k for k in messages if is_secret_key(k)], path
        assert not any("@" in v and "." in v.split("@")[-1] for v in messages.values()), (
            path
        )  # no e-mail addresses
