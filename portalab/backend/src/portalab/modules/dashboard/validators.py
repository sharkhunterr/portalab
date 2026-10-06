"""Dynamic validation of the dashboard settings against the registered widgets (T002, T024)."""

from typing import Any

from portalab.capabilities.dashboard import CONDITION_TYPES, WidgetRegistry
from portalab.modules.dashboard.settings import POLICIES, POLICY_CLASSES, STARTER


class DashboardValidators:
    def __init__(self, registry: WidgetRegistry) -> None:
        self.registry = registry

    def _known(self, key: str) -> bool:
        return self.registry.get(key) is not None

    async def policies(self, value: Any) -> list[str]:
        errors = []
        for key, policy in (value or {}).items():
            if not self._known(key):
                errors.append(f"unknown widget {key!r}")
                continue
            cls = policy.get("class") if isinstance(policy, dict) else None
            if cls not in POLICY_CLASSES:
                errors.append(f"{key}: class must be one of {', '.join(POLICY_CLASSES)}")
            allowed = {"class", "condition", "lockedConfig"} | (
                {"x", "y", "w", "h"} if cls == "pinned" else set()
            )
            extra = set(policy) - allowed if isinstance(policy, dict) else set()
            if extra:
                errors.append(f"{key}: unknown fields {sorted(extra)}")
            if cls == "conditional":
                condition = policy.get("condition")
                if not isinstance(condition, dict) or condition.get("type") not in CONDITION_TYPES:
                    errors.append(
                        f"{key}: a conditional policy needs a condition of type {', '.join(CONDITION_TYPES)}"
                    )
            if cls == "pinned":
                place = {k: policy.get(k) for k in ("x", "y", "w", "h")}
                if any(not isinstance(v, int) or isinstance(v, bool) for v in place.values()):
                    errors.append(f"{key}: a pinned widget needs whole numbers x, y, w and h")
                elif not (place["x"] >= 0 and 1 <= place["w"] <= 12 and place["x"] + place["w"] <= 12):
                    errors.append(f"{key}: a pinned widget stays inside the 12 columns")
                elif not (place["y"] >= 0 and 1 <= place["h"] <= 12):
                    errors.append(f"{key}: a pinned widget needs a row and a height")
            if "lockedConfig" in policy and not isinstance(policy["lockedConfig"], dict):
                errors.append(f"{key}: lockedConfig must be an object")
        return errors

    async def starter(self, value: Any) -> list[str]:
        errors = []
        for index, entry in enumerate(value or []):
            if not isinstance(entry, dict) or not self._known(str(entry.get("widget_key", ""))):
                errors.append(f"entry {index}: unknown widget")
                continue
            extra = set(entry) - {"widget_key", "w", "h", "roles"}
            if extra:
                errors.append(f"entry {index}: unknown fields {sorted(extra)}")
        return errors

    def table(self) -> dict[str, Any]:
        return {POLICIES: self.policies, STARTER: self.starter}
