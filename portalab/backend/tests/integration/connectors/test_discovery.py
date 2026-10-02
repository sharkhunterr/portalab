"""005 T018 — discovery probes only supplied targets; candidates need explicit confirm; decline keeps them
re-offerable; nothing is ever auto-enabled."""

import pytest

from portalab.connectors.fake import BACKENDS, FakeBackend
from portalab.core.errors import ValidationFailed
from tests.connectors_fixtures import TOKEN, ConnectorsHarness


async def test_discover_confirm_decline(cn: ConnectorsHarness) -> None:
    other = cn.base_url.replace("fake-", "other-")
    BACKENDS[other] = FakeBackend()
    unlisted = cn.base_url.replace("fake-", "unlisted-")
    BACKENDS[unlisted] = FakeBackend()

    found = await cn.module.discovery.discover(cn.admin, "fake", [cn.base_url, other, "http://nothing.lan"])
    assert sorted(item["target"] for item in found) == sorted([cn.base_url, other])  # unlisted never probed
    assert await cn.module.manager.list() == []  # discovery configures nothing

    by_target = {item["target"]: item["id"] for item in found}
    declined = await cn.module.discovery.decline(cn.admin, by_target[other])
    assert declined["status"] == "declined"
    again = await cn.module.discovery.discover(cn.admin, "fake", [other])
    assert [item["target"] for item in again] == [other]  # re-offered

    from uuid import UUID

    service_id = await cn.module.discovery.confirm(
        cn.admin, UUID(by_target[cn.base_url]), name="Found", secrets={"api_token": TOKEN}
    )
    view = await cn.module.manager.get(service_id)
    assert view.state == "configured" and view.config["base_url"] == cn.base_url  # never auto-enabled
    assert await cn.module.discovery.discover(cn.admin, "fake", [cn.base_url]) == []  # already a service
    assert len(await cn.outbox("connector.discovered")) == 3


async def test_targets_are_required(cn: ConnectorsHarness) -> None:
    with pytest.raises(ValidationFailed):
        await cn.module.discovery.discover(cn.admin, "fake", ["  "])
