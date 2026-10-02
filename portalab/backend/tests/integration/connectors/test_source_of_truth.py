"""005 T021 — removed at source ⇒ deactivated, never deleted; failed/partial syncs delete nothing;
conflicts resolved by the configured field priority with provenance kept."""

from typing import Any

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.config import EffectiveValue
from portalab.modules.connectors.sync.reconcile import FieldPriorities
from portalab.modules.connectors.sync.runner import source_ref
from tests.connectors_fixtures import ConnectorsHarness


async def _stored(cn: ConnectorsHarness, service_id: Any) -> dict[str, Any]:
    async with cn.full.database.session() as session:
        return cn.sink.stored(source_ref(await cn.module.manager._row(session, service_id)))


async def test_removed_at_source_is_deactivated(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    cn.remote.put("b", at=2)
    await cn.module.runner.run(service_id, kind="manual")
    cn.remote.remove("a")
    outcome = await cn.module.runner.run(service_id)
    assert outcome is not None and outcome.removed == 1
    rows = await _stored(cn, service_id)
    assert set(rows) == {"a", "b"} and rows["a"].active is False and rows["b"].active


async def test_failed_sync_deletes_nothing(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.put("a", at=1)
    cn.remote.put("b", at=2)
    await cn.module.runner.run(service_id, kind="manual")
    cn.remote.remove("a")
    cn.remote.put("c", at=3)
    cn.remote.put("d", at=4)
    cn.remote.fail_after = 1  # the source drops the connection mid-sync
    outcome = await cn.module.runner.run(service_id, kind="resync_full")
    assert outcome is not None and outcome.status == "failed" and outcome.removed == 0
    rows = await _stored(cn, service_id)
    assert rows["a"].active and rows["b"].active  # nothing deactivated by a failed run


class _Config:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    async def get(self, key: str, **_: Any) -> EffectiveValue:
        if key not in self.values:
            raise KeyError(key)
        return EffectiveValue(key, self.values[key], "global")


async def test_field_priority_and_provenance(cn: ConnectorsHarness) -> None:
    capabilities = cn.full.identity.capabilities
    capabilities.unregister("module:administration")
    capabilities.provide(
        CONFIG,
        _Config({"media.fieldPriority.movie.title": ["tmdb"], "media.fieldPriority.movie.rating": ["plex"]}),
        instance_ref="test",
        owner="test",
    )
    merged = await FieldPriorities(capabilities).reconcile(
        "movie",
        {
            "plex:1": {"title": "Local title", "rating": 7, "year": None},
            "tmdb:2": {"title": "Official title", "rating": 8, "year": 1999},
        },
    )
    assert merged.values == {"title": "Official title", "rating": 7, "year": 1999}
    assert merged.provenance == {"title": "tmdb:2", "rating": "plex:1", "year": "tmdb:2"}
