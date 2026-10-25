"""``PolicyOverlay`` (T023; R5, R6): the effective dashboard = policy (020 config) overlaid **on read** onto
the user's stored instances. Pure: stored rows are never modified, so tightening a policy never destroys a
user's choices and relaxing it restores them (CD-016 preserve/restore).

Classes: ``disabled`` (absent), ``mandatory`` (present, cannot be hidden/removed), ``locked`` (cannot be
moved/resized/reconfigured; ``lockedConfig`` forced), ``default`` (offered once when not yet placed),
``conditional`` (only when its condition holds), ``free``; 027 ``pinned`` — present for everyone at the
administrator's place and size (``x``, ``y``, ``w``, ``h``): neither removed, hidden, moved nor resized.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from portalab.capabilities.dashboard import Size, WidgetDefinition
from portalab.modules.dashboard.arrangement import Item, first_free, normalize
from portalab.modules.dashboard.arrangement import Size as GridSize


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
    x: int = 0  # desktop grid coordinates (027 R10)
    y: int = 0


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
    x: int = 0  # desktop grid coordinates (027 R10)
    y: int = 0
    # 027: what a member may still do with a widget the administrator pinned or locked
    movable: bool = True
    resizable: bool = True

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


MANDATORY = ("mandatory", "pinned")  # cannot be removed or hidden
LOCKED = ("locked", "pinned")  # cannot be moved, resized or reconfigured


def pin_of(policies: Mapping[str, Mapping[str, Any]], key: str) -> tuple[int, int, int, int] | None:
    """027: the place of a pinned widget (``x``, ``y`` on the 12-column grid, ``w``, ``h``)."""
    raw = policies.get(key) or {}
    if raw.get("class") != "pinned":
        return None
    try:
        w = max(1, min(12, int(raw.get("w", 6))))
        return (
            max(0, min(12 - w, int(raw.get("x", 0)))),
            max(0, int(raw.get("y", 0))),
            w,
            max(1, int(raw.get("h", 2))),
        )
    except (TypeError, ValueError):
        return 0, 0, 6, 2


def pin_freedom(policies: Mapping[str, Mapping[str, Any]], key: str) -> tuple[bool, bool]:
    """027: whether members may move (``move``) and resize (``resize``) a pinned widget — neither by
    default; it stays on their dashboard either way."""
    raw = policies.get(key) or {}
    if raw.get("class") != "pinned":
        return False, False
    return bool(raw.get("move", False)), bool(raw.get("resize", False))


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
        mandatory, locked = cls in MANDATORY, cls in LOCKED
        status = "active" if mandatory else row.status
        config: Mapping[str, Any] = row.config
        w, h = row.w, row.h
        x, y = row.x, row.y
        if definition is not None:
            size = definition.size.clamp(w, h)
            w, h = size.w, size.h
        pin = pin_of(policies, key)
        movable, resizable = pin_freedom(policies, key) if pin is not None else (not locked, not locked)
        if locked:
            locked_config = (policies.get(key) or {}).get("lockedConfig")
            if isinstance(locked_config, Mapping):
                config = {**config, **locked_config}
            if definition is not None and not resizable:
                w, h = definition.size.default.w, definition.size.default.h
        if pin is not None:
            if not movable:
                x, y = pin[0], pin[1]
            if not resizable:
                w, h = pin[2], pin[3]
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
                x,
                y,
                movable,
                resizable,
            )
        )
        placed.add(key)
    next_position = max((i.position for i in out.instances), default=-1) + 1
    for key, definition in sorted(definitions.items()):
        cls = policy_class(policies, key)
        if (
            key in placed
            or cls not in ("mandatory", "pinned", "default", "locked")
            or not allowed.get(key, False)
        ):
            continue
        if cls == "default" and starter_applied:
            continue  # defaults are offered with the starter dashboard, then left to the user
        if cls == "locked":
            continue  # locked ≠ forced: only constrains instances the user has
        default_size: Size = definition.size.default
        pin = pin_of(policies, key)
        # issue 250: the settings imposed with it, before the member has a row of their own
        imposed = (policies.get(key) or {}).get("lockedConfig") if pin is not None else None
        out.instances.append(
            EffectiveInstance(
                None,
                key,
                "active",
                next_position,
                pin[2] if pin else default_size.w,
                pin[3] if pin else default_size.h,
                {**definition.config_defaults, **(imposed if isinstance(imposed, Mapping) else {})},
                cls,
                pin is not None,
                cls in MANDATORY,
                True,
                pin[0] if pin else 0,
                pin[1] if pin else 0,
            )
        )
        next_position += 1
    out.instances = _arranged(out.instances, definitions)
    return out


def _arranged(
    instances: list[EffectiveInstance], definitions: Mapping[str, WidgetDefinition]
) -> list[EffectiveInstance]:
    """Effective desktop arrangement (027 R10): synthesized policy widgets take the first free slot, then
    the engine resolves overlaps (sizes forced by policy may collide) and compacts; ``position`` becomes the
    reading order — active widgets first, hidden ones keep their coordinates after them."""
    active = [i for i in instances if i.status == "active"]
    stored = [_item(index, i, definitions) for index, i in enumerate(active) if i.id is not None]
    for index, instance in enumerate(active):
        if instance.id is None and instance.policy == "pinned":
            stored.append(_item(index, instance, definitions))
    for index, instance in enumerate(active):
        if instance.id is None and instance.policy != "pinned":
            x, y = first_free(stored, instance.w, instance.h)
            stored.append(_item(index, replace(instance, x=x, y=y), definitions))
    by_key = {str(index): instance for index, instance in enumerate(active)}
    ordered = [replace(by_key[item.id], x=item.x, y=item.y, w=item.w, h=item.h) for item in normalize(stored)]
    hidden = [i for i in instances if i.status != "active"]
    return [replace(instance, position=index) for index, instance in enumerate([*ordered, *hidden])]


def _item(index: int, instance: EffectiveInstance, definitions: Mapping[str, WidgetDefinition]) -> Item:
    definition = definitions.get(instance.widget_key)
    limits = definition.size if definition is not None else None
    return Item(
        str(index),
        instance.x,
        instance.y,
        instance.w,
        instance.h,
        GridSize(limits.min.w, limits.min.h) if limits else None,
        GridSize(limits.max.w, limits.max.h) if limits else None,
        not instance.movable,
    )
