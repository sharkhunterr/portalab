"""023 T021 — the core works with ``plugins.enabled = false`` and with zero plugins installed; nothing in
the core imports plugins (import-linter contract); a missing or disabled plugin never breaks startup."""

import configparser
from dataclasses import replace
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_core_without_plugins(pl: PlHarness, client: AsyncClient) -> None:
    await login(client, "boss")
    for path in ("/api/v1/me", "/api/v1/admin/plugins", "/api/v1/plugins/pages", "/api/v1/me/permissions"):
        assert (await client.get(path)).status_code == 200, path
    assert (await client.get("/api/v1/admin/plugins")).json() == []
    pl.module.config = replace(pl.module.config, enabled=False)
    await pl.installed(pl.hello(), restart=False)
    assert await pl.module.lifecycle.load_enabled() == []
    await pl.module.start()  # startup with plugins off
    assert (await client.get("/api/v1/me")).status_code == 200


def test_core_has_no_path_to_plugins() -> None:
    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().parents[3] / "importlinter.ini")
    contract = config["importlinter:contract:core-no-plugins"]
    assert (
        "portalab.core" in contract["source_modules"] and "portalab.modules" in contract["forbidden_modules"]
    )
