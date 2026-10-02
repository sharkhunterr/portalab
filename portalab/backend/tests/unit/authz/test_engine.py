"""003 T011 — engine decisions: default deny, union of role+group grants, explicit deny wins, order
independence, Admin = all enabled permissions minus denies, disabled permissions never grant."""

import random
from uuid import uuid4

import pytest

from portalab.modules.authz.engine.engine import AuthorizationEngine, PermissionInfo
from portalab.modules.authz.grants.store import EffectiveGrants, GrantRow

pytestmark = pytest.mark.unit

SUBJECT = uuid4()


def info(key: str = "news.publish", *, reserved: bool = False, enabled: bool = True) -> PermissionInfo:
    return PermissionInfo(key, enabled, sensitive=False, reserved=reserved, requires_confirmation=False)


def grants(*rows: GrantRow, admin: bool = False) -> EffectiveGrants:
    return EffectiveGrants(SUBJECT, admin, frozenset(), frozenset(), tuple(rows))


def allow(key: str = "news.publish", scope: str = "global", ref: str = "") -> GrantRow:
    return GrantRow(key, "allow", scope, ref)


def deny(key: str = "news.publish", scope: str = "global", ref: str = "") -> GrantRow:
    return GrantRow(key, "deny", scope, ref)


decide = AuthorizationEngine._decide


def test_default_deny() -> None:
    decision = decide(info(), grants(), SUBJECT, None)
    assert not decision.allowed and decision.reason == "no_grant"


def test_grant_allows_and_other_permissions_stay_denied() -> None:
    held = grants(allow())
    assert decide(info(), held, SUBJECT, None).allowed
    assert not decide(info("news.delete"), held, SUBJECT, None).allowed


def test_union_of_role_and_group_grants() -> None:
    held = grants(allow("news.read"), allow("wiki.edit"))  # one from a role, one from a group
    assert decide(info("news.read"), held, SUBJECT, None).allowed
    assert decide(info("wiki.edit"), held, SUBJECT, None).allowed


def test_explicit_deny_wins() -> None:
    decision = decide(info(), grants(allow(), deny()), SUBJECT, None)
    assert not decision.allowed and decision.reason == "explicit_deny"


def test_order_independence() -> None:
    rows = [allow(), deny(), allow("news.read"), allow(scope="owned"), deny("wiki.edit")]
    expected = {
        key: decide(info(key), grants(*rows), SUBJECT, None)
        for key in ("news.publish", "news.read", "wiki.edit")
    }
    for seed in range(30):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)  # noqa: S311 — test permutations
        for key, decision in expected.items():
            assert decide(info(key), grants(*shuffled), SUBJECT, None) == decision


def test_admin_holds_every_enabled_permission_minus_denies() -> None:
    assert decide(info("anything.at_all"), grants(admin=True), SUBJECT, None).reason == "admin"
    assert decide(info("users.admin.transfer", reserved=True), grants(admin=True), SUBJECT, None).allowed
    assert not decide(info(), grants(deny(), admin=True), SUBJECT, None).allowed


def test_reserved_is_admin_only_even_with_a_row() -> None:
    decision = decide(
        info("users.admin.transfer", reserved=True), grants(allow("users.admin.transfer")), SUBJECT, None
    )
    assert not decision.allowed and decision.reason == "reserved"


async def test_disabled_and_unknown_permissions_never_grant() -> None:
    engine = AuthorizationEngine.__new__(AuthorizationEngine)

    async def permission(key: str) -> PermissionInfo | None:
        return {"news.publish": info(enabled=False)}.get(key)

    async def effective(subject: object) -> EffectiveGrants:
        return grants(allow(), admin=True)

    engine._permission = permission  # type: ignore[method-assign]
    engine._grants = effective  # type: ignore[method-assign]
    from portalab.core.authz_port import Principal

    assert (
        await engine._evaluate(Principal(user_id=SUBJECT), "news.publish", None)
    ).reason == "permission_disabled"
    assert (
        await engine._evaluate(Principal(user_id=SUBJECT), "nope.nope", None)
    ).reason == "unknown_permission"
