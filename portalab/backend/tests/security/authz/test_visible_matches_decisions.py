"""Issue 404 — ``visible()`` (one batch, for what a page shows) never says more than the decision itself: for
an administrator, a plain member, a member with an explicit deny, the AI channel without ``ai.use``, and an
unknown or disabled permission, it holds exactly the permissions ``is_allowed`` grants globally. It writes no
audit entry (the action is audited when it is called); and within a request the catalog and the grants are
read once, even by checks running side by side."""

import asyncio

import pytest
from sqlalchemy import func, select, text

from portalab.core.authorization import authorization_scope
from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import AuthzPlatform, ai, insert_user, make_admin, user

pytestmark = pytest.mark.integration


async def test_visible_says_no_more_than_the_decisions(platform: AuthzPlatform) -> None:
    engine = platform.authz.engine
    admin, member = [await insert_user(platform.database) for _ in range(2)]
    await make_admin(platform, admin)
    async with platform.database.session() as session:
        keys = list((await session.execute(text("SELECT key FROM authz.permissions ORDER BY key"))).scalars())
        await session.execute(text("UPDATE authz.permissions SET enabled = false WHERE key = 'news.create'"))
        await session.commit()
    wanted = [*keys, "no.such.permission"]

    async def parity() -> set[str]:
        shown: set[str] = set()
        for principal in (user(admin), user(member), ai(member)):
            with authorization_scope():
                shown = await engine.visible(principal, wanted)
            with authorization_scope():
                decided = {k for k in wanted if await engine.is_allowed(principal, k)}
            assert shown == decided, principal
            assert "no.such.permission" not in shown and "news.create" not in shown
        with authorization_scope():
            return await engine.visible(user(member), wanted)

    assert "news.read" in await parity()  # the plain member reads the news
    async with platform.database.session() as session:  # the User role's grant turned into a deny
        await session.execute(
            text(
                "UPDATE authz.grants SET effect = 'deny' WHERE permission_key = 'news.read'"
                " AND holder_kind = 'role' AND holder_id = (SELECT id FROM authz.roles WHERE key = 'user')"
            )
        )
        await session.commit()
    assert "news.read" not in await parity()  # an explicit deny wins, in both

    async with platform.database.session() as session:
        before = await session.scalar(select(func.count()).select_from(AuditEntry))
    with authorization_scope():
        assert await engine.visible(user(admin), keys)
    async with platform.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(AuditEntry)) == before  # nothing audited


async def test_checks_side_by_side_read_the_catalog_once(platform: AuthzPlatform) -> None:
    engine = platform.authz.engine
    member = await insert_user(platform.database)
    calls = 0
    real = engine._catalog

    async def counted():  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return await real()

    engine._catalog = counted  # type: ignore[method-assign]
    with authorization_scope():
        await asyncio.gather(
            *(engine.is_allowed(user(member), k) for k in ("news.read", "media.read", "users.read"))
        )
    assert calls == 1
