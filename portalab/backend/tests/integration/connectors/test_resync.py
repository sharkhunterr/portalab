"""005 T028 — a full resync reconciles only that service's provenance, never native data or other
services; a large deletion ratio needs confirmation; requests are audited; the API asks for confirmation."""

from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.record_sink import ServiceRef
from portalab.connectors.fake import BACKENDS, EPOCH, FakeBackend
from portalab.modules.connectors.sync.runner import DELETION_CONFIRMATION, source_ref
from tests.connectors_fixtures import ConnectorsHarness, admin_client


async def _ref(cn: ConnectorsHarness, service_id: Any) -> ServiceRef:
    async with cn.full.database.session() as session:
        return source_ref(await cn.module.manager._row(session, service_id))


async def test_full_resync_scope_and_ratio_guard(cn: ConnectorsHarness) -> None:
    other_url = cn.base_url.replace("fake-", "other-")
    BACKENDS[other_url] = FakeBackend()
    service_id = await cn.enabled("Main")
    other_id = await cn.enabled("Other", base_url=other_url)
    for index in range(10):
        cn.remote.put(f"m{index}", at=index + 1)
    BACKENDS[other_url].put("o1", at=1)
    await cn.module.runner.run(service_id, kind="manual")
    await cn.module.runner.run(other_id, kind="manual")
    native = ServiceRef(service_id=service_id, source_system="portal:native")  # native portal data
    await cn.sink.upsert([SourceRecord("portal", "n1", "item", {"title": "mine"}, EPOCH)], native)

    for index in range(5):  # the source silently lost half of its items (no explicit removal)
        cn.remote.items.pop(f"m{index}")
    held = await cn.module.runner.run(service_id, kind="resync_full")
    assert held is not None and held.status == "partial" and held.removed == 0
    assert held.last_error == DELETION_CONFIRMATION and held.withheld_removals == 5

    applied = await cn.module.runner.run(service_id, kind="resync_full", allow_large_deletion=True)
    assert applied is not None and applied.status == "succeeded" and applied.removed == 5
    rows = cn.sink.stored(await _ref(cn, service_id))
    assert sorted(k for k, r in rows.items() if not r.active) == [f"m{i}" for i in range(5)]
    assert all(r.active for r in cn.sink.stored(await _ref(cn, other_id)).values())  # other service untouched
    assert cn.sink.stored(native)["n1"].active  # native portal data untouched


async def test_small_full_resync_applies_without_confirmation(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    for index in range(10):
        cn.remote.put(f"m{index}", at=index + 1)
    await cn.module.runner.run(service_id, kind="manual")
    cn.remote.items.pop("m0")
    outcome = await cn.module.runner.run(service_id, kind="resync_full")
    assert outcome is not None and outcome.status == "succeeded" and outcome.removed == 1


async def test_resync_api_requires_confirmation_for_full(
    app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness
) -> None:
    service_id = await cn.enabled()
    await admin_client(app, client, cn)
    partial = await client.post(f"/api/v1/services/{service_id}/resync", json={"mode": "partial"})
    assert partial.status_code == 202, partial.text
    first = await client.post(f"/api/v1/services/{service_id}/resync", json={"mode": "full"})
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    token = first.json()["confirmation"]
    mismatched = await client.post(
        f"/api/v1/services/{service_id}/resync",
        json={"mode": "full", "allow_large_deletion": True, "confirmation": token},
    )
    assert mismatched.status_code == 403  # the confirmation is bound to the exact request
    first = await client.post(f"/api/v1/services/{service_id}/resync", json={"mode": "full"})
    done = await client.post(
        f"/api/v1/services/{service_id}/resync",
        json={"mode": "full", "confirmation": first.json()["confirmation"]},
    )
    assert done.status_code == 202, done.text
    async with cn.full.database.session() as session:
        kinds = (
            await session.execute(
                text(
                    "SELECT payload->>'kind' FROM core.job "
                    "WHERE kind = 'connectors.sync_service' ORDER BY created_at"
                )
            )
        ).scalars()
        audited = (
            await session.execute(
                text(
                    "SELECT count(*) FROM audit.audit_entries WHERE action = 'connector.resync_requested' "
                    "AND resource_id = :id"
                ),
                {"id": str(service_id)},
            )
        ).scalar()
    assert sorted(kinds) == ["resync_full", "resync_partial"] and audited == 2


async def test_manual_sync_api_and_history(
    app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness
) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    await admin_client(app, client, cn)
    queued = await client.post(f"/api/v1/services/{service_id}/sync")
    assert queued.status_code == 202 and queued.json()["queued"] is True
    async with cn.full.database.session() as session:
        payload = await session.scalar(
            text("SELECT payload FROM core.job WHERE kind = 'connectors.sync_service'")
        )
    await cn.module.scheduler.handle(payload)
    runs = await client.get(f"/api/v1/services/{service_id}/sync-runs")
    assert runs.status_code == 200 and [(r["kind"], r["added"]) for r in runs.json()["items"]] == [
        ("manual", 1)
    ]
    await cn.module.manager.disable(cn.admin, service_id)
    refused = await client.post(f"/api/v1/services/{service_id}/sync")
    assert refused.status_code == 409 and refused.json()["code"] == "service.disabled"
