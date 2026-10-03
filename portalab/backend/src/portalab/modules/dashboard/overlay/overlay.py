"""``PolicyOverlay`` (T023; R5, R6): the effective dashboard = policy (020 config) overlaid **on read** onto
the user's stored instances. Pure: stored rows are never modified, so tightening a policy never destroys a
user's choices and relaxing it restores them (CD-016 preserve/restore).

Classes: ``disabled`` (absent), ``mandatory`` (present, cannot be hidden/removed), ``locked`` (cannot be
moved/resized/reconfigured; ``lockedConfig`` forced), ``default`` (offered once when not yet placed),
``conditional`` (only when its condition holds), ``free``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from portalab.capabilities.dashboard import Size, WidgetDefinition


@dataclass(frozen=True, slots=True)
class StoredInstance:
    id: UUID | None
    widget_key: str
    status: str  # active | hidden
    position: int
    w: int
    h: int
    config: Mapping[str, Any]
    origin: str = "user"


@dataclass(frozen=True, slots=True)
class EffectiveInstance:
    id: UUID | None  # None: synthesized by policy, not stored
    widget_key: str
    status: str
    position: int
    w: int
    h: int
    config: Mapping[str, Any]
    policy: str = "free"
    locked: bool = False
    mandatory: bool = False
    available: bool = True  # False: definition gone (plugin disabled) → placeholder

    @property
    def removable(self) -> bool:
        return not self.mandatory

    @property
    def hideable(self) -> bool:
        return not self.mandatory


@dataclass
class Overlay:
    instances: list[EffectiveInstance] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


def policy_class(policies: Mapping[str, Mapping[str, Any]], key: str) -> str:
    raw = policies.get(key) or {}
    value = raw.get("class", "free")
    return value if isinstance(value, str) else "free"


def effective(
    rows: Sequence[StoredInstance],
    policies: Mapping[str, Mapping[str, Any]],
    definitions: Mapping[str, WidgetDefinition],
    allowed: Mapping[str, bool],
    conditions: Mapping[str, bool],
    *,
    starter_applied: bool = True,
) -> Overlay:
    """``allowed[key]``: permission/module/entitlement for this user; ``conditions[key]``: evaluated policy
    conditions (missing ⇒ true). Definitions absent from ``definitions`` are kept as placeholders."""
    out = Overlay()
    placed: set[str] = set()
    for row in sorted(rows, key=lambda r: (r.position, str(r.id))):
        key = row.widget_key
        cls = policy_class(policies, key)
        definition = definitions.get(key)
        if cls == "disabled":
            continue
        if definition is not None and not allowed.get(key, False):
            continue  # permission/module/entitlement withdrawn: hidden, the row is kept
        if cls == "conditional" and not conditions.get(key, True):
            continue
        mandatory, locked = cls == "mandatory", cls == "locked"
        status = "active" if mandatory else row.status
        config: Mapping[str, Any] = row.config
        w, h = row.w, row.h
        if definition is not None:
            size = definition.size.clamp(w, h)
            w, h = size.w, size.h
        if locked:
            locked_config = (policies.get(key) or {}).get("lockedConfig")
            if isinstance(locked_config, Mapping):
                config = {**config, **locked_config}
            if definition is not None:
                w, h = definition.size.default.w, definition.size.default.h
        out.instances.append(
            EffectiveInstance(
                row.id,
                key,
                status,
                row.position,
                w,
                h,
                config,
                cls,
                locked,
                mandatory,
                definition is not None,
            )
        )
        placed.add(key)
    next_position = max((i.position for i in out.instances), default=-1) + 1
    for key, definition in sorted(definitions.items()):
        cls = policy_class(policies, key)
        if key in placed or cls not in ("mandatory", "default", "locked") or not allowed.get(key, False):
            continue
        if cls == "default" and starter_applied:
            continue  # defaults are offered with the starter dashboard, then left to the user
        if cls == "locked":
            continue  # locked ≠ forced: only constrains instances the user has
        default_size: Size = definition.size.default
        out.instances.append(
            EffectiveInstance(
                None,
                key,
                "active",
                next_position,
                default_size.w,
                default_size.h,
                dict(definition.config_defaults),
                cls,
                False,
                cls == "mandatory",
            )
        )
        next_position += 1
    out.instances = [replace(instance, position=index) for index, instance in enumerate(out.instances)]
    return out
