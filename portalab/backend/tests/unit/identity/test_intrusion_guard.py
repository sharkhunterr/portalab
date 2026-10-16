"""issue 1: who probes what they may not reach is blocked — the points, the limits, the block's end."""

from portalab.modules.identity.guard import IntrusionGuard, weigh


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_what_counts() -> None:
    assert weigh("/api/v1/me", "", 200) is None
    assert weigh("/api/v1/media/x", "", 404) is None  # a missing page is not an attack
    assert weigh("/api/v1/admin/users", "", 404) == (1, "unknown administration address")
    assert weigh("/api/v1/marketplace/products/x", "", 403) == (1, "refused")
    assert weigh("/api/v1/admin/visuals", "", 403) == (2, "refused on the administration")
    for attack in ("/api/v1/visuals/files/p/s/../../state.json", "/api/v1/x/%2e%2e/y", "/api/v1/x%00.png"):
        assert weigh(attack, "", 404) == (8, "attack-shaped address")
    assert weigh("/api/v1/search", "q=<script>alert(1)</script>", 200) is not None


def test_a_session_probing_the_administration_is_blocked_then_let_go() -> None:
    clock = Clock()
    guard = IntrusionGuard(clock=clock)
    keys = ["ip:10.0.0.9", "session:abc"]
    started = []
    for _ in range(10):
        started += guard.strike(keys, 2, "refused on the administration", "/api/v1/admin/x")
    assert [b.key for b in started] == ["session:abc"]  # the address has a much higher limit
    assert guard.blocked(["session:abc"]) is not None
    assert guard.blocked(["ip:10.0.0.9"]) is None
    clock.now += 901
    assert guard.blocked(["session:abc"]) is None  # a block ends


def test_points_fade_after_the_window() -> None:
    clock = Clock()
    guard = IntrusionGuard(clock=clock)
    for _ in range(19):
        guard.strike(["session:s"], 1, "refused", "/api/v1/x")
        clock.now += 40  # 19 refusals spread over 12 minutes: never 20 in 10
    assert guard.blocked(["session:s"]) is None


def test_an_address_trying_many_accounts_is_blocked() -> None:
    guard = IntrusionGuard(clock=Clock())
    for index in range(8):
        guard.strike(["ip:10.0.0.7", f"session:{index}"], 8, "attack-shaped address", "/api/v1/../x")
    assert guard.blocked(["ip:10.0.0.7"]) is not None


def test_administrators_lift_a_block() -> None:
    guard = IntrusionGuard(clock=Clock())
    for _ in range(3):
        guard.strike(["session:s"], 8, "attack-shaped address", "/a/../b")
    assert [b["key"] for b in guard.blocks()] == ["session:s"]
    assert guard.lift("session:s") == 1 and guard.blocked(["session:s"]) is None


def test_an_anonymous_visitor_listing_the_administration_counts() -> None:
    assert weigh("/api/v1/admin/users", "", 401) == (1, "unknown administration address")
    assert weigh("/api/v1/me", "", 401) is None


def test_blocks_stored_elsewhere_are_enforced_and_lifted_ones_let_go() -> None:
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from uuid import uuid4

    clock = Clock()
    guard = IntrusionGuard(clock=clock)
    wall = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    row = SimpleNamespace(
        id=uuid4(), kind="address", subject="203.0.113.9", label="203.0.113.9", reason="attack",
        points=64, paths=["/api/v1/x"], until=wall + timedelta(minutes=10),
    )  # fmt: skip
    account = SimpleNamespace(
        id=uuid4(), kind="account", subject="u1", label="mallory", reason="refused", points=20, paths=[],
        until=wall + timedelta(minutes=10),
    )  # fmt: skip
    guard.load([row, account], wall=wall)
    assert guard.blocked(["ip:203.0.113.9"]) is not None and guard.user_blocked("u1") is not None
    # one just started here, not stored yet, survives a load; the stored ones lifted elsewhere go
    for _ in range(3):
        guard.strike(["session:s"], 8, "attack-shaped address", "/a/../b")
    guard.load([], wall=wall)
    assert guard.blocked(["ip:203.0.113.9"]) is None and guard.user_blocked("u1") is None
    assert guard.blocked(["session:s"]) is not None


def test_the_administrator_s_thresholds() -> None:
    guard = IntrusionGuard(clock=Clock())
    guard.configure(session_limit=5, block_seconds=60)
    started = []
    for _ in range(5):
        started += guard.strike(["session:t"], 1, "refused", "/api/v1/x")
    assert [b.key for b in started] == ["session:t"]
