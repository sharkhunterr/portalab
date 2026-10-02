"""004 T005 — admin layout > user order (when allowed) > manifest hint; deterministic ties."""

from portalab.capabilities.navigation import NavigationContribution
from portalab.modules.shell.assembler.layout import arrange


def entry(key: str, owner: str = "module:m", hint: int = 100, group: str = "main") -> NavigationContribution:
    prefix = "plugin.p." if owner.startswith("plugin") else "m."
    return NavigationContribution(
        key=f"{prefix}{key}",
        owner=owner,
        kind="entry",
        label_key=key,
        route=f"/{key}",
        order_hint=hint,
        group=group,
        required_permission="x.read",
    )


def keys(groups: list[dict[str, object]]) -> list[list[str]]:
    return [[e.key for e in g["entries"]] for g in groups]  # type: ignore[attr-defined]


def test_precedence() -> None:
    a, b, c = entry("a", hint=30), entry("b", hint=20), entry("c", hint=10)
    assert keys(arrange([a, b, c])) == [["m.c", "m.b", "m.a"]]  # manifest hint
    assert keys(arrange([a, b, c], user_order=["m.a", "m.b"])) == [["m.a", "m.b", "m.c"]]  # user order
    assert keys(arrange([a, b, c], user_order=["m.a"], allow_user_ordering=False)) == [["m.c", "m.b", "m.a"]]
    layout = {"order": {"m.b": 0}}
    assert keys(arrange([a, b, c], layout=layout, user_order=["m.a", "m.b"])) == [
        ["m.b", "m.a", "m.c"]
    ]  # admin wins
    assert keys(arrange([a, b, c], layout={"pinned": ["m.a"]})) == [["m.a", "m.c", "m.b"]]


def test_ties_and_conflicts_are_deterministic() -> None:
    plugin = entry("x", owner="plugin:p", hint=10)
    module = entry("y", hint=10)
    first = keys(arrange([plugin, module]))
    assert first == [["m.y", "plugin.p.x"]]  # modules before plugins on equal hints
    assert all(keys(arrange([module, plugin])) == first for _ in range(5))


def test_groups_and_admin_regrouping() -> None:
    a, b = entry("a", group="main"), entry("b", group="admin")
    groups = arrange([a, b], layout={"groups_of": {"m.b": "main"}, "group_order": ["main"]})
    assert [g["key"] for g in groups] == ["main"] and keys(groups) == [["m.a", "m.b"]]
    assert [g["key"] for g in arrange([a, b], layout={"group_order": ["admin", "main"]})] == ["admin", "main"]
