"""Pure resolution of an effective setting value (T009; R2, CD-011, CD-016).

Order (later wins): code default ▸ global ▸ module ▸ plugin ▸ user. Admin policies constrain only the user
tier: ``lock`` ignores user values, ``bound`` ignores user values outside the bounds; the user's own value is
never deleted — it is *retained* and becomes effective again as soon as the policy is removed.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from portalab.capabilities.config import EffectiveValue, SourceScope

MISSING: Any = object()


@dataclass(frozen=True, slots=True)
class PolicyView:
    mode: str  # default | lock | bound
    bounds: Mapping[str, Any] | None = None


def within_bounds(value: Any, bounds: Mapping[str, Any] | None) -> bool:
    """``{"allowed": [...]}`` and/or ``{"min": n, "max": m}`` (numeric values only)."""
    if not bounds:
        return True
    if "allowed" in bounds and value not in bounds["allowed"]:
        return False
    if "min" in bounds or "max" in bounds:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return False
        if "min" in bounds and value < bounds["min"]:
            return False
        if "max" in bounds and value > bounds["max"]:
            return False
    return True


def resolve(
    key: str,
    default: Any,
    stored: Mapping[str, Any],
    *,
    user_overridable: bool,
    policy: PolicyView | None = None,
) -> EffectiveValue:
    """``stored`` maps scope (``global|module|plugin|user``) to a value or :data:`MISSING`."""
    value, source = default, "default"
    for scope in ("global", "module", "plugin"):
        candidate = stored.get(scope, MISSING)
        if candidate is not MISSING:
            value, source = candidate, scope
    locked = policy is not None and policy.mode == "lock"
    user_value = stored.get("user", MISSING)
    retained = False
    if user_overridable and user_value is not MISSING:
        if locked or (
            policy is not None and policy.mode == "bound" and not within_bounds(user_value, policy.bounds)
        ):
            retained = True
        else:
            value, source = user_value, "user"
    typed_source: SourceScope = source  # type: ignore[assignment]
    return EffectiveValue(key, value, typed_source, locked=locked, user_value_retained=retained)
