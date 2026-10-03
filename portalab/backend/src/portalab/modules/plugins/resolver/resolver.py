"""Dependency resolution (T011; R9, FR-020): a graph from manifests — missing dependencies and version
ranges are named, cycles are refused, the load order is topological and deterministic (ties by key), and
disabling a plugin with enabled dependents is blocked (``plugin.has_dependents``) unless the Admin confirms
the cascade, previewed here."""

from collections.abc import Mapping
from dataclasses import dataclass

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from portalab.core.errors import Conflict
from portalab.modules.plugins.manifest.schema import Manifest


class DependencyCycle(Conflict):
    default_code = "plugin.dependency_cycle"
    default_title = "Dependency cycle"


@dataclass(frozen=True, slots=True)
class Problem:
    code: str  # dependency_missing | dependency_incompatible | dependency_disabled | dependency_cycle
    plugin: str
    detail: str


def problems_for(
    key: str, manifests: Mapping[str, Manifest], enabled: set[str] | None = None
) -> list[Problem]:
    """What prevents ``key`` from being enabled (dependencies only)."""
    manifest = manifests[key]
    out: list[Problem] = []
    for requirement in manifest.requires_plugins:
        dependency = manifests.get(requirement["key"])
        if dependency is None:
            out.append(Problem("dependency_missing", requirement["key"], f"{key} needs {requirement['key']}"))
            continue
        wanted = requirement.get("range")
        if wanted and Version(dependency.version) not in SpecifierSet(wanted):
            out.append(
                Problem(
                    "dependency_incompatible",
                    requirement["key"],
                    f"{key} needs {requirement['key']} {wanted}, found {dependency.version}",
                )
            )
        elif enabled is not None and requirement["key"] not in enabled:
            out.append(
                Problem("dependency_disabled", requirement["key"], f"{requirement['key']} is not enabled")
            )
    cycle = find_cycle(manifests, start=key)
    if cycle:
        out.append(Problem("dependency_cycle", key, " → ".join(cycle)))
    return out


def find_cycle(manifests: Mapping[str, Manifest], start: str | None = None) -> list[str]:
    graph = {
        k: sorted(r["key"] for r in m.requires_plugins if r["key"] in manifests) for k, m in manifests.items()
    }
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return [*stack[stack.index(nxt) :], nxt]
            if state.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return []

    for node in [start] if start is not None else sorted(graph):
        if node is not None and state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return []


def load_order(manifests: Mapping[str, Manifest], priority: Mapping[str, int] | None = None) -> list[str]:
    """Dependencies first; deterministic — among plugins ready together, by ``(priority, key)`` (R11)."""
    cycle = find_cycle(manifests)
    if cycle:
        raise DependencyCycle("Plugins depend on each other in a cycle.", extensions={"cycle": cycle})
    pending = {
        k: {r["key"] for r in m.requires_plugins if r["key"] in manifests} for k, m in manifests.items()
    }
    order: list[str] = []
    while pending:
        ready = sorted(
            (k for k, deps in pending.items() if not deps), key=lambda k: ((priority or {}).get(k, 100), k)
        )
        for key in ready:
            order.append(key)
            del pending[key]
        for deps in pending.values():
            deps.difference_update(ready)
    return order


def dependents(key: str, manifests: Mapping[str, Manifest], enabled: set[str]) -> list[str]:
    """Enabled plugins that (transitively) need ``key`` — the cascade a disable would cause."""
    direct = {
        k for k, m in manifests.items() if k in enabled and any(r["key"] == key for r in m.requires_plugins)
    }
    out = set(direct)
    for dependent in direct:
        out.update(dependents(dependent, manifests, enabled))
    return [k for k in load_order({k: manifests[k] for k in out})][::-1] if out else []
