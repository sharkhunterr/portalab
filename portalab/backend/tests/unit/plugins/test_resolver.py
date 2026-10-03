"""023 T009 — dependency graph: missing and incompatible ranges named, cycles refused, deterministic
topological order, dependents (cascade preview); randomized graphs keep every dependency before its
dependent."""

import random

import pytest

from portalab.modules.plugins.manifest.schema import Manifest, validate
from portalab.modules.plugins.resolver.resolver import (
    DependencyCycle,
    dependents,
    find_cycle,
    load_order,
    problems_for,
)


def m(key: str, version: str = "1.0.0", *requires: tuple[str, str | None]) -> Manifest:
    return validate(
        {
            "key": key,
            "name": key,
            "version": version,
            "requires_plugins": [{"key": k, **({"range": r} if r else {})} for k, r in requires],
        }
    )


def test_problems_named() -> None:
    graph = {
        "aa": m("aa", "1.0.0", ("bb", ">=2.0")),
        "bb": m("bb", "1.5.0"),
        "cc": m("cc", "1.0.0", ("zz", None)),
    }
    assert [p.code for p in problems_for("aa", graph)] == ["dependency_incompatible"]
    assert "bb >=2.0" in problems_for("aa", graph)[0].detail
    assert [p.code for p in problems_for("cc", graph)] == ["dependency_missing"]
    graph["aa"] = m("aa", "1.0.0", ("bb", ">=1.0"))
    assert [p.code for p in problems_for("aa", graph, enabled=set())] == ["dependency_disabled"]
    assert problems_for("aa", graph, enabled={"bb"}) == []


def test_cycles_and_order() -> None:
    cyclic = {"aa": m("aa", "1.0.0", ("bb", None)), "bb": m("bb", "1.0.0", ("aa", None))}
    assert find_cycle(cyclic) in (["aa", "bb", "aa"], ["bb", "aa", "bb"])
    with pytest.raises(DependencyCycle):
        load_order(cyclic)
    graph = {
        "app": m("app", "1.0.0", ("lib", None), ("core", None)),
        "lib": m("lib", "1.0.0", ("core", None)),
        "core": m("core"),
        "other": m("other"),
    }
    assert load_order(graph) == ["core", "other", "lib", "app"]
    assert dependents("core", graph, {"app", "lib", "core"}) == ["app", "lib"]
    assert dependents("core", graph, {"core", "lib"}) == ["lib"]
    assert dependents("other", graph, set(graph)) == []


@pytest.mark.parametrize("seed", range(25))
def test_random_dags(seed: int) -> None:
    rng = random.Random(seed)  # noqa: S311 — deterministic test graphs
    keys = [f"p{i:02d}" for i in range(rng.randint(2, 12))]
    graph = {}
    for index, key in enumerate(keys):
        deps = rng.sample(keys[:index], k=min(index, rng.randint(0, 3)))
        graph[key] = m(key, "1.0.0", *((d, None) for d in deps))
    order = load_order(graph)
    assert sorted(order) == sorted(keys) and order == load_order(dict(reversed(list(graph.items()))))
    position = {k: i for i, k in enumerate(order)}
    for key, manifest in graph.items():
        assert all(position[r["key"]] < position[key] for r in manifest.requires_plugins)
