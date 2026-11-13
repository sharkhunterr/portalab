"""Issue 410 — the Version page: the version from the source, the build, whether a newer release is out on
GitHub (asked through a fake GitHub here; the Admin can turn the check off) and the security posture — for
the administrators only."""

from collections.abc import Iterable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import portalab
from portalab.modules.administration import system_info
from portalab.modules.administration.backup.service import BackupService
from tests.authz_fixtures import TEST_APPLICATION_KEY, make_admin
from tests.integration.admin.settings_fixture import test_settings  # noqa: F401 — fixture
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("test_settings")]


class Heads:
    async def current(self) -> set[str]:
        return {"identity_0005"}

    async def compare(self, archive_heads: Iterable[str]) -> str:
        return "same"

    async def prepare(self, archive_heads: Iterable[str]) -> None: ...

    async def finish(self) -> None: ...


@pytest.fixture(autouse=True)
def backups(full: FullPlatform, tmp_path: Path) -> None:
    async def site() -> str:
        return "Portalab"

    admin = full.administration
    admin.backups = BackupService(  # type: ignore[attr-defined]
        admin.database,
        tmp_path,
        TEST_APPLICATION_KEY,
        admin.capabilities,
        full.authz.audit,
        versions=Heads(),
        site=site,
        portalab=portalab.__version__,
    )


async def _admin(app: FastAPI, full: FullPlatform, client: httpx.AsyncClient) -> None:
    await make_admin(full, await create_user(module_of(app), "boss"))
    await login(client, "boss")


@pytest.fixture
def fake_github(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"tag_name": "v99.0.0", "published_at": "2026-11-13T18:00:00Z"})

    check = system_info.UpdateCheck(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(system_info, "UPDATES", check)
    return seen


async def test_the_version_page(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform, fake_github: list[httpx.Request]
) -> None:
    await _admin(app, full, client)
    answer = await client.get("/api/v1/admin/system/version")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["portalab"] == portalab.__version__
    assert set(body["build"]) == {"commit", "date"}
    assert body["update"]["latest"] == "99.0.0" and body["update"]["update_available"] is True
    keys = {point["key"]: point for point in body["security"]}
    assert keys["transport"]["level"] == "ok"  # the test client speaks HTTPS
    assert keys["mfa"]["values"] == {"own": False, "members": 0} and keys["mfa"]["level"] == "warn"
    assert keys["backup"]["level"] == "warn"

    forced = await client.post("/api/v1/admin/system/version/check")
    assert forced.status_code == 200 and forced.json()["latest"] == "99.0.0"
    assert len(fake_github) == 2


async def test_the_check_can_be_turned_off(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform, fake_github: list[httpx.Request]
) -> None:
    await _admin(app, full, client)
    off = await client.put(
        "/api/v1/admin/config", json={"changes": [{"key": "admin.updateCheck", "value": False}]}
    )
    assert off.status_code < 300, off.text
    body = (await client.get("/api/v1/admin/system/version")).json()
    assert body["update"] == {"enabled": False, "current": portalab.__version__}
    assert (await client.post("/api/v1/admin/system/version/check")).json()["enabled"] is False
    assert fake_github == []


async def test_members_are_refused(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform, fake_github: list[httpx.Request]
) -> None:
    await make_admin(full, await create_user(module_of(app), "boss"))
    await create_user(module_of(app), "bob")
    await login(client, "bob")
    assert (await client.get("/api/v1/admin/system/version")).status_code == 403
    assert (await client.post("/api/v1/admin/system/version/check")).status_code == 403
    assert fake_github == []
