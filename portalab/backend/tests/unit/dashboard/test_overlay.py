"""009 T021 — overlay precedence: free/default/mandatory/locked/conditional/disabled; mandatory cannot be
hidden; locked placement/config forced; disabled absent; conditional only when true; withdrawn permission
hides; stored rows never mutated; tightening then relaxing a policy restores the user's prior state."""

import itertools
from uuid import uuid4

from portalab.modules.dashboard.overlay.overlay import StoredInstance, effective
from tests.unit.dashboard.fakes import definition

DEFS = {key: definition(key) for key in ("a.one", "a.two", "a.three")}
ALLOWED = dict.fromkeys(DEFS, True)


def rows() -> list[StoredInstance]:
    return [
        StoredInstance(uuid4(), "a.one", "active", 0, 4, 2, {"limit": 3}),
        StoredInstance(uuid4(), "a.two", "hidden", 1, 6, 3, {"limit": 7}),
    ]


def keys(overlay: object) -> list[tuple[str, str]]:
    return [(i.widget_key, i.status) for i in overlay.instances]  # type: ignore[attr-defined]


def test_free_keeps_user_choices() -> None:
    stored = rows()
    out = effective(stored, {}, DEFS, ALLOWED, {})
    assert keys(out) == [("a.one", "active"), ("a.two", "hidden")]
    assert out.instances[1].config == {"limit": 7} and out.instances[1].hideable


def test_mandatory_disabled_locked_conditional() -> None:
    stored = rows()
    policies = {
        "a.one": {"class": "locked", "lockedConfig": {"limit": 1}},
        "a.two": {"class": "mandatory"},
        "a.three": {"class": "mandatory"},
    }
    out = effective(stored, policies, DEFS, ALLOWED, {})
    by = {i.widget_key: i for i in out.instances}
    assert (
        by["a.one"].locked and by["a.one"].config == {"limit": 1} and (by["a.one"].w, by["a.one"].h) == (4, 2)
    )
    assert by["a.two"].status == "active" and not by["a.two"].removable  # hidden by the user, forced visible
    assert by["a.three"].id is None and by["a.three"].mandatory  # synthesized, not stored
    assert keys(effective(stored, {"a.one": {"class": "disabled"}}, DEFS, ALLOWED, {}))[0][0] == "a.two"
    conditional = {"a.one": {"class": "conditional", "condition": {"type": "permission", "value": "x"}}}
    assert "a.one" not in [
        k for k, _ in keys(effective(stored, conditional, DEFS, ALLOWED, {"a.one": False}))
    ]
    assert "a.one" in [k for k, _ in keys(effective(stored, conditional, DEFS, ALLOWED, {"a.one": True}))]
    withdrawn = effective(stored, {}, DEFS, {**ALLOWED, "a.one": False}, {})
    assert [k for k, _ in keys(withdrawn)] == ["a.two"]
    gone = effective(stored, {}, {"a.two": DEFS["a.two"]}, ALLOWED, {})
    assert [(i.widget_key, i.available) for i in gone.instances] == [("a.one", False), ("a.two", True)]


def test_tighten_then_relax_restores_and_never_mutates() -> None:
    stored = rows()
    snapshot = list(stored)
    baseline = effective(stored, {}, DEFS, ALLOWED, {})
    classes = ["free", "default", "mandatory", "locked", "conditional", "disabled"]
    for one, two in itertools.product(classes, repeat=2):
        policies = {"a.one": {"class": one, "lockedConfig": {"limit": 9}}, "a.two": {"class": two}}
        effective(stored, policies, DEFS, ALLOWED, {"a.one": False, "a.two": False})
        assert stored == snapshot  # stored rows never touched
        relaxed = effective(stored, {}, DEFS, ALLOWED, {})
        assert relaxed == baseline


def test_default_offered_only_before_the_starter() -> None:
    policies = {"a.three": {"class": "default"}}
    assert "a.three" in [
        k for k, _ in keys(effective([], policies, DEFS, ALLOWED, {}, starter_applied=False))
    ]
    assert "a.three" not in [
        k for k, _ in keys(effective([], policies, DEFS, ALLOWED, {}, starter_applied=True))
    ]
