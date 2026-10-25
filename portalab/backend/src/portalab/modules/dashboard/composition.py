"""Issue 250 — the default dashboard as the administrator composes it: every widget a new dashboard (or
« Default ») gets, at its place, with its settings and how far it is locked — read from, and written as, the
two settings that hold it (the widget policies and the starter layout).

Three locks, simply: ``free`` (the member changes it or removes it: a starter entry), ``always`` (always
there, moved and set by the member, never removed: a mandatory policy and its starter place) and ``locked``
(there, at this place, this size, with these settings: a pinned policy). The other widgets are offered to
members, or switched off for everyone (``disabled``). A conditional policy is the administrator's own and is
kept.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from portalab.modules.dashboard.arrangement import Item, flow, normalize
from portalab.modules.dashboard.overlay.overlay import pin_freedom, pin_of, policy_class

LOCKS = ("free", "always", "locked")
VIEWS = ("tablet", "phone")
PLACE = ("x", "y", "w", "h")


def read(
    policies: Mapping[str, Mapping[str, Any]],
    starter: Sequence[Mapping[str, Any]],
    defaults: Mapping[str, tuple[int, int, Mapping[str, Any]]],
) -> dict[str, Any]:
    """``defaults[key]``: a registered widget's default width, height and settings (others are skipped)."""
    items: list[dict[str, Any]] = []
    pinned: list[Item] = []
    for key in sorted(policies):
        pin = pin_of(policies, key)
        if pin is None or key not in defaults:
            continue
        move, resize = pin_freedom(policies, key)
        locked = dict((policies.get(key) or {}).get("lockedConfig") or {})
        items.append(
            {
                "widget_key": key,
                **dict(zip(PLACE, pin, strict=True)),
                "config": {**defaults[key][2], **locked},
                "lock": "locked",
                **({"move": True} if move else {}),
                **({"resize": True} if resize else {}),
            }
        )
        pinned.append(Item(key, *pin, locked=True))
    entries: list[dict[str, Any]] = []
    for entry in starter:
        key = str(entry.get("widget_key", ""))
        if key not in defaults or any(i["widget_key"] == key for i in [*items, *entries]):
            continue
        cls = policy_class(policies, key)
        if cls == "disabled":
            continue
        entries.append(
            {
                "widget_key": key,
                "w": int(entry.get("w") or defaults[key][0]),
                "h": int(entry.get("h") or defaults[key][1]),
                **({"x": int(entry["x"]), "y": int(entry["y"])} if "x" in entry and "y" in entry else {}),
                "config": {**defaults[key][2], **dict(entry.get("config") or {})},
                "lock": "always" if cls in ("mandatory", "locked") else "free",
                **{view: dict(entry[view]) for view in VIEWS if isinstance(entry.get(view), Mapping)},
                **({"roles": list(entry["roles"])} if entry.get("roles") else {}),
            }
        )
    # what a first visit gets without a place of its own: the widgets offered by default, the mandatory ones
    for key in sorted(defaults):
        cls = policy_class(policies, key)
        if cls in ("default", "mandatory") and all(i["widget_key"] != key for i in [*items, *entries]):
            w, h, config = defaults[key]
            entries.append({"widget_key": key, "w": w, "h": h, "config": dict(config), "lock": _lock_of(cls)})
    placed = all("x" in e for e in entries)
    grid = [Item(e["widget_key"], e.get("x", 0), e.get("y", 0), e["w"], e["h"]) for e in entries]
    settled = normalize([*pinned, *grid]) if placed else normalize([*pinned, *flow(grid, around=pinned)])
    at = {i.id: i for i in settled}
    for entry in entries:
        cell = at[entry["widget_key"]]
        entry.update(x=cell.x, y=cell.y, w=cell.w, h=cell.h)
    disabled = sorted(k for k in defaults if policy_class(policies, k) == "disabled")
    return {"items": [*items, *entries], "disabled": disabled}


def _lock_of(cls: str) -> str:
    return "always" if cls == "mandatory" else "free"


def write(
    items: Sequence[Mapping[str, Any]],
    disabled: Sequence[str],
    policies: Mapping[str, Mapping[str, Any]],
    defaults: Mapping[str, tuple[int, int, Mapping[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """The policies and the starter layout of a composition (the conditional policies kept)."""
    out: dict[str, dict[str, Any]] = {
        key: dict(policy) for key, policy in policies.items() if policy_class(policies, key) == "conditional"
    }
    starter: list[dict[str, Any]] = []
    for item in items:
        key = str(item["widget_key"])
        lock = item.get("lock", "free")
        place = {k: int(item[k]) for k in PLACE}
        own = _own(item.get("config") or {}, defaults.get(key, (0, 0, {}))[2])
        if lock == "locked":
            out[key] = {
                "class": "pinned",
                **place,
                **({"move": True} if item.get("move") else {}),
                **({"resize": True} if item.get("resize") else {}),
                **({"lockedConfig": own} if own else {}),
            }
            continue
        if lock == "always":
            out[key] = {"class": "mandatory"}
        else:
            out.pop(key, None)  # a free widget placed: no policy of its own
        starter.append(
            {
                "widget_key": key,
                **place,
                **({"config": own} if own else {}),
                **{view: {k: int(item[view][k]) for k in PLACE} for view in VIEWS if item.get(view)},
                **({"roles": list(item["roles"])} if item.get("roles") else {}),
            }
        )
    placed = {str(i["widget_key"]) for i in items}
    for key in disabled:
        if key not in placed:
            out[key] = {"class": "disabled"}
    return out, starter


def _own(config: Mapping[str, Any], defaults: Mapping[str, Any]) -> dict[str, Any]:
    """Only the settings that differ from the widget's defaults (a later default then reaches everyone)."""
    return {k: v for k, v in config.items() if k not in defaults or defaults[k] != v}
