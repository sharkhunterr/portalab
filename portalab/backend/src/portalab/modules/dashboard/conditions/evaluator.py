"""``ConditionEvaluator`` (T023; R7): the closed set ``role_in``, ``permission``, ``service_state``,
``campaign_active``, ``module_enabled``, ``data_present`` — evaluated server-side. An unknown or
unevaluable condition hides the widget and leaves a diagnostic (never an error, never an expression)."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.administration import EXTENSION_STATE_CAPABILITY
from portalab.capabilities.dashboard import CONDITION_TYPES, Condition
from portalab.capabilities.health import SERVICE_STATE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.authz_port import Authorizer, Principal

DataProbe = Callable[[str, Principal], Awaitable[bool]]


@dataclass
class Evaluation:
    passed: bool
    diagnostics: list[str] = field(default_factory=list)


def parse_condition(raw: Any) -> Condition | None:
    if isinstance(raw, Condition):
        return raw
    if isinstance(raw, Mapping) and isinstance(raw.get("type"), str):
        return Condition(str(raw["type"]), raw.get("value"))
    return None


class ConditionEvaluator:
    def __init__(
        self,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        *,
        data_present: DataProbe | None = None,
    ) -> None:
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.data_present = data_present

    def _provider(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def evaluate_all(self, conditions: Sequence[Condition], principal: Principal) -> Evaluation:
        result = Evaluation(True)
        for condition in conditions:
            ok, diagnostic = await self.evaluate(condition, principal)
            if diagnostic:
                result.diagnostics.append(diagnostic)
            if not ok:
                result.passed = False
        return result

    async def evaluate(self, condition: Condition, principal: Principal) -> tuple[bool, str | None]:
        if condition.type not in CONDITION_TYPES:
            return False, f"unknown condition {condition.type!r}"
        try:
            return await asyncio.wait_for(self._evaluate(condition, principal), timeout=2)
        except Exception:
            return False, f"condition {condition.type} could not be evaluated"

    async def _evaluate(self, condition: Condition, principal: Principal) -> tuple[bool, str | None]:
        value = condition.value
        match condition.type:
            case "permission":
                return bool(
                    isinstance(value, str) and await self.authorizer.is_allowed(principal, value)
                ), None
            case "role_in":
                roles = self._provider(ROLES_CAPABILITY)
                user = principal.acting_for or principal.user_id
                if roles is None or user is None:
                    return False, "roles are not available"
                wanted = {value} if isinstance(value, str) else set(value or ())
                return bool(wanted & set(await roles.roles_of(user))), None
            case "service_state":
                states = self._provider(SERVICE_STATE)
                if states is None or not isinstance(value, Mapping):
                    return False, "service states are not available"
                view = await states.get(str(value.get("service_id", "")))
                states_wanted = value.get("states") or [value.get("state")]
                return bool(view is not None and view.state in states_wanted), None
            case "module_enabled":
                extensions = self._provider(EXTENSION_STATE_CAPABILITY)
                if extensions is None:
                    return True, None  # without toggles every installed module is enabled
                return bool(await extensions.enabled("module", str(value))), None
            case "campaign_active":
                return False, "campaigns are not available yet (spec 014)"
            case "data_present":
                if self.data_present is None or not isinstance(value, str):
                    return False, "data presence cannot be checked"
                return await self.data_present(value, principal), None
        return False, f"unknown condition {condition.type!r}"
