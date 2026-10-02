"""Ordering & grouping (T008; R5, FR-009). Precedence: admin layout (``shell.navigation.layout``) > user
order (``shell.navigation.userOrder``, when ``allowUserOrdering``) > manifest ``order_hint``; ties are broken
deterministically by ``(order_hint, owner priority, key)`` — modules before plugins — so conflicting
contributions resolve identically on every run."""

from collections.abc import Mapping, Sequence
from typing import Any

from portalab.capabilities.navigation import NavigationContribution

UNRANKED = 1_000_000


def _owner_priority(owner: str) -> int:
    return 0 if owner.startswith("module:") else 1


def sort_key(
    entry: NavigationContribution, admin_order: Mapping[str, int], user_rank: Mapping[str, int]
) -> tuple[int, int, int, int, str]:
    return (
        admin_order.get(entry.key, UNRANKED),
        user_rank.get(entry.key, UNRANKED),
        entry.order_hint,
        _owner_priority(entry.owner),
        entry.key,
    )


def arrange(
    entries: Sequence[NavigationContribution],
    *,
    layout: Mapping[str, Any] | None = None,
    user_order: Sequence[str] = (),
    allow_user_ordering: bool = True,
) -> list[dict[str, Any]]:
    """Group and order entries; returns ``[{key, label_key, entries: [...]}]``."""
    layout = layout or {}
    admin_order = {str(k): int(v) for k, v in dict(layout.get("order", {})).items()}
    pinned = [str(k) for k in layout.get("pinned", [])]
    group_of = {str(k): str(v) for k, v in dict(layout.get("groups_of", {})).items()}
    group_order = [str(g) for g in layout.get("group_order", [])]
    for index, key in enumerate(pinned):
        admin_order.setdefault(key, -len(pinned) + index)
    user_rank = {key: index for index, key in enumerate(user_order)} if allow_user_ordering else {}
    ordered = sorted(entries, key=lambda e: sort_key(e, admin_order, user_rank))
    groups: dict[str, list[NavigationContribution]] = {}
    for entry in ordered:
        groups.setdefault(group_of.get(entry.key, entry.group), []).append(entry)
    names = sorted(
        groups,
        key=lambda g: (
            group_order.index(g) if g in group_order else UNRANKED,
            groups[g] and sort_key(groups[g][0], admin_order, user_rank),
            g,
        ),
    )
    return [{"key": name, "label_key": f"nav.group.{name}", "entries": groups[name]} for name in names]
