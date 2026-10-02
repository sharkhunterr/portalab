"""025 T016 — AI observability carries counts, latency, outcome, provider/model, tools and actions, and
**no prompt or response content** anywhere in the observability store."""

import inspect

from sqlalchemy import text

from portalab.capabilities.observability import report_ai_call
from tests.observability_fixtures import ObsHarness

SECRET_PROMPT = "please summarize my private diary entry about Alice"


def test_reporting_api_has_no_content_parameter() -> None:
    parameters = set(inspect.signature(report_ai_call).parameters)
    assert parameters == {"provider", "model", "latency_ms", "outcome", "tools", "actions", "registry"}


async def test_ai_metrics_and_no_content(ob: ObsHarness) -> None:
    for outcome in ("ok", "ok", "error", "timeout"):
        report_ai_call(
            provider="local",
            model="llama",
            latency_ms=420.0,
            outcome=outcome,
            tools=["search"],
            actions=1,
            registry=ob.hooks,
        )  # type: ignore[arg-type]
    ob.hooks.error("ai", "provider_error", RuntimeError("provider failed"), context={"provider": "local"})
    await ob.module.collector.flush()
    ai = {e.component: e for e in await ob.module.evaluator.evaluate_all()}["ai"]
    facts = ai.reason["functional"][0]["facts"]
    assert facts == {"requests": 4, "failed": 2, "failure_rate": 0.5} and ai.functional == "degraded"
    parts: list[str] = []
    async with ob.database.session() as session:
        for table in ("metric_samples", "errors", "component_health", "health_history", "anomalies"):
            rows = (await session.execute(text(f"SELECT * FROM obs.{table}"))).all()
            parts.extend(str(row) for row in rows)
    dump = " ".join(parts)
    assert SECRET_PROMPT not in dump and "diary" not in dump
