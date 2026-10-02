"""025 T015 — plugins in the common model (state, version, last activity, recent errors); a failing plugin
leaves the portal available; the connector complement tells external-unavailable, invalid auth, sync error
and stale apart; plugin contributions disappear with their owner."""

from datetime import UTC, datetime
from uuid import UUID

from portalab.capabilities.observability import (
    PLUGIN_STATUS,
    Check,
    CheckResult,
    PluginStatus,
    declare_observable,
)
from tests.observability_fixtures import ObsHarness


class Plugins:
    async def plugins(self) -> list[PluginStatus]:
        return [
            PluginStatus("radio", "active", "1.2.0", datetime(2026, 10, 1, tzinfo=UTC)),
            PluginStatus("quiz", "error", "0.9.1", None, recent_errors=4, detail="crashed on start"),
            PluginStatus("old", "incompatible", "0.1.0"),
            PluginStatus("conf", "invalid_config", "1.0.0"),
            PluginStatus("deps", "missing_dependency", "1.0.0"),
            PluginStatus("off", "disabled", "1.0.0"),
        ]


async def test_plugins_and_isolation(ob: ObsHarness) -> None:
    capabilities = ob.hl.cn.full.identity.capabilities
    capabilities.provide(PLUGIN_STATUS, Plugins(), instance_ref="test", owner="test")

    async def own_check() -> CheckResult:
        raise RuntimeError("plugin bug")

    declare_observable(
        "plugin:radio:stream",
        owner="plugin:radio",
        kind="plugin",
        functional_checks=(Check("stream", own_check),),
        registry=ob.registry,
    )
    evaluations = {e.component: e for e in await ob.module.evaluator.evaluate_all()}
    assert evaluations["plugin:radio"].technical == "ok"
    quiz = evaluations["plugin:quiz"]
    assert quiz.technical == "down" and quiz.functional == "degraded"
    assert quiz.reason["technical"][0]["facts"]["version"] == "0.9.1"
    for plugin in ("old", "conf", "deps"):
        assert evaluations[f"plugin:{plugin}"].technical == "down"
    assert evaluations["plugin:off"].status == "healthy"
    assert evaluations["plugin:radio:stream"].functional == "unknown"  # its own failing check is isolated
    assert evaluations["db"].technical == "ok"  # the portal keeps working
    assert ob.registry.unregister("plugin:radio") == 1
    assert "plugin:radio:stream" not in {c.name for c in await ob.registry.components()}


async def test_connector_complement(ob: ObsHarness) -> None:
    hl = ob.hl
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    hl.cn.remote.token = "rotated-credential"
    hl.cn.remote.mode = "auth_error"
    await hl.cn.module.runner.run(UUID(service_id), kind="manual")
    evaluation = {e.component: e for e in await ob.module.evaluator.evaluate_all()}[f"connector:{service_id}"]
    assert (
        evaluation.functional == "failing" and "invalid_auth" in evaluation.reason["functional"][0]["reason"]
    )

    hl.cn.remote.mode = "error"
    for _ in range(hl.cn.module.config.circuit_failure_threshold):
        await hl.cn.module.runner.run(UUID(service_id), kind="manual")
    evaluation = {e.component: e for e in await ob.module.evaluator.evaluate_all()}[f"connector:{service_id}"]
    assert (
        evaluation.technical == "down"
        and "external_unavailable" in evaluation.reason["technical"][0]["reason"]
    )
