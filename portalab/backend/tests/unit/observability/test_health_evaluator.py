"""025 T011 — two-axis health: technical ok + functional failing is degraded (never healthy); axes are
independent; an evaluator failure is unknown, not green."""

import asyncio

import pytest

from portalab.capabilities.observability import Check, CheckResult, ObservedComponent
from portalab.modules.observability.components.evaluator import evaluate_component, reported_status


def _check(state: str, name: str = "c") -> Check:
    async def run() -> CheckResult:
        return CheckResult(state, f"{name} is {state}")  # type: ignore[arg-type]

    return Check(name, run)


def _broken() -> Check:
    async def run() -> CheckResult:
        raise RuntimeError("boom")

    return Check("broken", run)


def _slow() -> Check:
    async def run() -> CheckResult:
        await asyncio.sleep(10)
        return CheckResult("ok")

    return Check("slow", run)


@pytest.mark.parametrize(
    ("technical", "functional", "status"),
    [
        (["ok"], ["ok"], "healthy"),
        (["ok"], ["failing"], "degraded"),
        (["ok"], ["degraded"], "degraded"),
        (["down"], ["ok"], "down"),
        (["ok", "degraded"], ["ok"], "degraded"),
        (["ok"], ["ok", "unknown"], "degraded"),
    ],
)
async def test_table(technical: list[str], functional: list[str], status: str) -> None:
    component = ObservedComponent(
        "x",
        "test",
        technical_checks=tuple(_check(s, f"t{i}") for i, s in enumerate(technical)),
        functional_checks=tuple(_check(s, f"f{i}") for i, s in enumerate(functional)),
    )
    evaluation = await evaluate_component(component)
    assert evaluation.status == status


async def test_failures_are_unknown_not_green(monkeypatch: pytest.MonkeyPatch) -> None:
    import portalab.modules.observability.components.evaluator as evaluator

    monkeypatch.setattr(evaluator, "CHECK_TIMEOUT_SECONDS", 0.05)
    component = ObservedComponent(
        "x", "test", technical_checks=(_check("ok"),), functional_checks=(_broken(),)
    )
    evaluation = await evaluate_component(component)
    assert (evaluation.technical, evaluation.functional, evaluation.status) == ("ok", "unknown", "degraded")
    slow = await evaluator.run_check(_slow(), 0.05)
    assert slow.state == "unknown" and "in time" in slow.reason


async def test_axis_mapping_and_unobserved() -> None:
    component = ObservedComponent("x", "test", functional_checks=(_check("down"),))
    evaluation = await evaluate_component(component)
    assert evaluation.functional == "failing" and evaluation.technical == "unknown"
    assert evaluation.reason["unobserved"] == ["technical"]
    assert reported_status("unknown", "unknown") == "unknown"
