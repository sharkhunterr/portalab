"""028 (FR-037): the health checks answer the machine itself and the declared networks only; the first run
answers nothing once the portal is set up; the terms of use are read after signing in."""

import httpx
import pytest

from portalab.app.main import create_app
from portalab.app.security import address_in, networks_of
from portalab.core.db import Database
from portalab.core.settings import SettingsError, load_settings

pytestmark = pytest.mark.integration


def _client(app: object, host: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(host, 1234))  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_answers_local_networks_only(database: Database, heads: set[str]) -> None:
    app = create_app(database=database, migration_heads=heads)
    async with _client(app, "127.0.0.1") as local:
        assert (await local.get("/healthz")).status_code == 200
    async with _client(app, "192.168.1.20") as lan:
        assert (await lan.get("/healthz")).status_code == 200
    async with _client(app, "203.0.113.9") as outside:
        refused = await outside.get("/healthz")
        assert refused.status_code == 401 and refused.json()["code"] == "unauthorized"
        assert (await outside.get("/readyz")).status_code == 401


def test_networks_and_proxies_are_bootstrap_settings(tmp_path: object) -> None:
    networks = networks_of(["10.0.0.0/8", "::1/128"])
    assert address_in("10.2.3.4", networks) and not address_in("8.8.8.8", networks)
    assert not address_in("not-an-address", networks)
    from pathlib import Path

    key = Path(str(tmp_path)) / "key"
    key.write_text("k" * 64)
    base = {"DATABASE_URL": "postgresql://u:p@h/db", "SECRET_KEY_FILE": str(key)}
    settings = load_settings({**base, "HEALTH_NETWORKS": "127.0.0.1/32", "TRUSTED_PROXIES": "10.0.0.5"})
    assert settings.health_networks == ("127.0.0.1/32",) and settings.trusted_proxies == ("10.0.0.5",)
    with pytest.raises(SettingsError):
        load_settings({**base, "HEALTH_NETWORKS": "everyone"})
