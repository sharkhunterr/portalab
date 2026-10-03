"""009 T022 — the closed condition catalog (role_in, permission, service_state, campaign_active stub,
module_enabled, data_present); an unknown condition hides the widget with a diagnostic; no free-form
expressions are evaluated."""

from datetime import UTC, datetime
from uuid import uuid4

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.catalog import new_registry
from portalab.capabilities.dashboard import Condition
from portalab.capabilities.health import SERVICE_STATE, ServiceStateView
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.authz_port import Principal
from portalab.modules.dashboard.conditions.evaluator import ConditionEvaluator
from tests.unit.dashboard.fakes import Authorizer

ME = Principal(user_id=uuid4())
AT = datetime(2026, 10, 5, tzinfo=UTC)


class Roles:
    async def roles_of(self, user_id: object) -> frozenset[str]:
        return frozenset({"user", "editor"})


class States:
    async def get(self, service_id: str) -> ServiceStateView | None:
        return ServiceStateView(service_id, "degraded", AT, AT, 0.9, AT) if service_id == "s1" else None

    async def all(self) -> list[ServiceStateView]:
        return []


class Extensions:
    async def enabled(self, kind: str, ref: str) -> bool:
        return ref != "wiki"


async def data(key: str, principal: Principal) -> bool:
    return key == "health.services_summary"


async def test_catalog() -> None:
    capabilities = new_registry()
    capabilities.provide(ROLES_CAPABILITY, Roles(), instance_ref="t", owner="module:authz")
    capabilities.provide(SERVICE_STATE, States(), instance_ref="t", owner="module:health")
    capabilities.provide(
        EXTENSION_STATE_CAPABILITY, Extensions(), instance_ref="t", owner="module:administration"
    )
    evaluator = ConditionEvaluator(Authorizer({"services.read"}), capabilities, data_present=data)
    cases = [
        (Condition("permission", "services.read"), True),
        (Condition("permission", "audit.read"), False),
        (Condition("role_in", ["editor", "moderator"]), True),
        (Condition("role_in", "admin"), False),
        (Condition("service_state", {"service_id": "s1", "states": ["degraded", "unavailable"]}), True),
        (Condition("service_state", {"service_id": "s2", "state": "operational"}), False),
        (Condition("module_enabled", "media"), True),
        (Condition("module_enabled", "wiki"), False),
        (Condition("data_present", "health.services_summary"), True),
        (Condition("campaign_active", "halloween"), False),
    ]
    for condition, expected in cases:
        assert (await evaluator.evaluate(condition, ME))[0] is expected, condition


async def test_unknown_and_unavailable_conditions_hide_with_diagnostics() -> None:
    evaluator = ConditionEvaluator(Authorizer(), new_registry())
    result = await evaluator.evaluate_all(
        [
            Condition("eval", "__import__('os')"),
            Condition("role_in", "admin"),
            Condition("permission", "users.self.manage"),
        ],
        ME,
    )
    assert not result.passed
    assert any("unknown condition" in d for d in result.diagnostics)
    assert any("roles are not available" in d for d in result.diagnostics)
