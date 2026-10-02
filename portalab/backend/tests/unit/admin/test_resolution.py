"""020 T008 — resolution order code default ▸ global ▸ module ▸ plugin ▸ user within policy; locked keys
ignore user values; bounds; the user value is retained and effective again once the policy is removed."""

import itertools
import random

import pytest

from portalab.modules.administration.config.resolution import MISSING, PolicyView, resolve, within_bounds

pytestmark = pytest.mark.unit

ORDER = ("global", "module", "plugin", "user")


@pytest.mark.parametrize("present", [set(c) for n in range(5) for c in itertools.combinations(ORDER, n)])
def test_later_scope_wins(present: set[str]) -> None:
    stored = {scope: f"{scope}-value" if scope in present else MISSING for scope in ORDER}
    effective = resolve("k", "default", stored, user_overridable=True)
    expected = next((scope for scope in reversed(ORDER) if scope in present), "default")
    assert effective.source == expected
    assert effective.value == ("default" if expected == "default" else f"{expected}-value")


def test_user_tier_only_when_overridable() -> None:
    effective = resolve("k", 1, {"global": 2, "user": 3}, user_overridable=False)
    assert (effective.value, effective.source) == (2, "global")


def test_lock_retains_the_user_value() -> None:
    stored = {"global": "light", "user": "dark"}
    locked = resolve("ui.theme", "auto", stored, user_overridable=True, policy=PolicyView("lock"))
    assert (locked.value, locked.locked, locked.user_value_retained) == ("light", True, True)
    restored = resolve("ui.theme", "auto", stored, user_overridable=True, policy=None)
    assert (restored.value, restored.source) == ("dark", "user")


def test_bound_policy() -> None:
    policy = PolicyView("bound", {"min": 1, "max": 10})
    assert resolve("k", 5, {"user": 7}, user_overridable=True, policy=policy).value == 7
    out = resolve("k", 5, {"user": 70}, user_overridable=True, policy=policy)
    assert (out.value, out.user_value_retained) == (5, True)
    assert within_bounds("fr", {"allowed": ["fr", "en"]}) and not within_bounds(
        "de", {"allowed": ["fr", "en"]}
    )
    assert not within_bounds("x", {"min": 1}) and not within_bounds(True, {"max": 3})


def test_random_resolution_is_deterministic() -> None:
    rng = random.Random(7)  # noqa: S311 — test data
    for _ in range(200):
        stored = {scope: rng.choice([MISSING, rng.randint(0, 9)]) for scope in ORDER}
        policy = rng.choice(
            [None, PolicyView("lock"), PolicyView("bound", {"max": 5}), PolicyView("default")]
        )
        first = resolve("k", -1, stored, user_overridable=True, policy=policy)
        assert first == resolve(
            "k", -1, dict(reversed(list(stored.items()))), user_overridable=True, policy=policy
        )
