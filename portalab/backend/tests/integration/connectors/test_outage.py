"""005 T026 — repeated failures open the breaker ⇒ ``unavailable``; last-known data served as stale;
half-open probe recovers; unrelated services unaffected; sync state and health reported separately."""

from datetime import timedelta

from portalab.capabilities.results import Available, Stale
from portalab.connectors.fake import BACKENDS, CAPABILITY, FakeBackend
from portalab.core.time import FixedClock
from tests.connectors_fixtures import ConnectorsHarness


def _provider(cn: ConnectorsHarness, service_id: object) -> object:
    for registration in cn.full.identity.capabilities.system_providers(CAPABILITY):
        if registration.instance_ref == str(service_id):
            return registration.provider
    raise AssertionError("not provided")


async def test_outage_stale_and_recovery(cn: ConnectorsHarness, clock: FixedClock) -> None:
    other_url = cn.base_url.replace("fake-", "healthy-")
    BACKENDS[other_url] = FakeBackend()
    failing = await cn.enabled("Failing")
    healthy = await cn.enabled("Healthy", base_url=other_url)
    cn.remote.put("a", title="A")
    provider: object = _provider(cn, failing)
    assert isinstance(await provider.list_items(), Available)  # type: ignore[attr-defined]

    cn.remote.mode = "error"
    for _ in range(2):  # threshold = 2 in the harness
        assert isinstance(await provider.list_items(), Stale)  # type: ignore[attr-defined]
    view = await cn.module.manager.get(failing)
    assert view.state == "unavailable" and view.health == "open" and view.stale
    assert view.sync["status"] == "idle"  # sync state is reported apart from health
    calls = cn.remote.calls
    stale = await provider.list_items()  # type: ignore[attr-defined]
    assert (
        isinstance(stale, Stale) and stale.value == [{"id": "a", "title": "A"}] and cn.remote.calls == calls
    )
    assert (await cn.module.manager.get(healthy)).state == "enabled"  # unrelated service unaffected

    cn.remote.mode = "ok"
    clock.advance(timedelta(seconds=61))  # half-open probe
    assert isinstance(await provider.list_items(), Available)  # type: ignore[attr-defined]
    assert (await cn.module.manager.get(failing)).state == "enabled"
    states = [e["to_state"] for e in await cn.outbox("service.status_changed")]
    assert states == ["unavailable", "enabled"]


async def test_scheduled_sync_skipped_while_open(cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    cn.remote.mode = "error"
    for _ in range(2):
        outcome = await cn.module.runner.run(service_id, kind="manual")
        assert outcome is not None and outcome.status == "failed"
    assert (await cn.module.manager.get(service_id)).state == "unavailable"
    assert await cn.module.runner.run(service_id) is None


async def test_restart_while_unavailable_recovers_on_the_first_answer(cn: ConnectorsHarness) -> None:
    """027: the portal restarted while a service was out — its circuit starts closed, so it never
    « recovers » through the breaker; the first answer of the service brings it back to ``enabled``."""
    service_id = await cn.enabled()
    assert await cn.module.manager.set_condition(service_id, "unavailable", reason="circuit breaker open")
    cn.module.manager.breakers.forget(str(service_id))  # what a restart leaves: a fresh, closed circuit
    cn.remote.put("a", title="A")
    assert isinstance(await _provider(cn, service_id).list_items(), Available)  # type: ignore[attr-defined]
    view = await cn.module.manager.get(service_id)
    assert view.state == "enabled" and view.state_reason == "service recovered"
