"""003 T026 — sensitive allow *and* deny decisions are audited (actor, action, resource, scope, decision,
correlation id); non-sensitive denials are not; context is redacted; audit failure ⇒ refused (fail closed)."""

import pytest
from sqlalchemy import select

from portalab.core.audit_port import AuditError, AuditRecord
from portalab.core.authz_port import ResourceRef
from portalab.core.logging import correlation_scope
from portalab.modules.authz.audit.store import bounded_context
from portalab.modules.authz.engine.engine import AuditFailed
from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import AuthzPlatform, insert_user, make_admin, user


async def _entries(platform: AuthzPlatform) -> list[AuditEntry]:
    async with platform.database.session() as session:
        return list((await session.execute(select(AuditEntry).order_by(AuditEntry.seq))).scalars())


async def test_sensitive_allow_and_deny_are_audited(platform: AuthzPlatform) -> None:
    admin, member = await insert_user(platform.database), await insert_user(platform.database)
    await make_admin(platform, admin)
    before = len(await _entries(platform))
    resource = ResourceRef("user", str(member))
    with correlation_scope("corr-audit-1"):
        assert await platform.authz.engine.is_allowed(user(admin), "users.manage", resource)
        assert not await platform.authz.engine.is_allowed(user(member), "users.manage", resource)
        assert not await platform.authz.engine.is_allowed(user(member), "news.create")  # not sensitive
    entries = (await _entries(platform))[before:]
    assert [(e.action, e.decision, e.actor_user_id) for e in entries] == [
        ("authorize:users.manage", "allow", admin),
        ("authorize:users.manage", "deny", member),
    ]
    assert entries[0].resource_type == "user" and entries[0].resource_id == str(member)
    assert entries[0].scope == "global" and entries[0].correlation_id == "corr-audit-1"
    assert entries[1].context["reason"] == "no_grant"


async def test_context_is_redacted_and_bounded(platform: AuthzPlatform) -> None:
    await platform.authz.audit.record(
        None,
        AuditRecord(
            action="test.redaction", actor=None, context={"password": "hunter2-secret", "note": "ok"}
        ),
    )
    entry = (await _entries(platform))[-1]
    assert entry.context["password"] != "hunter2-secret" and entry.context["note"] == "ok"
    assert entry.actor_kind == "anonymous"
    assert bounded_context({"blob": "x" * 10_000}, 512) == {"truncated": True, "keys": ["blob"]}


async def test_audit_failure_refuses_sensitive_actions(platform: AuthzPlatform) -> None:
    admin = await insert_user(platform.database)
    await make_admin(platform, admin)

    class Broken:
        async def record(self, session: object, entry: AuditRecord) -> None:
            raise AuditError("disk full")

    platform.authz.engine.audit = Broken()  # type: ignore[assignment]
    with pytest.raises(AuditFailed):
        await platform.authz.engine.is_allowed(user(admin), "users.manage")
    assert await platform.authz.engine.is_allowed(user(admin), "news.read")  # non-sensitive unaffected
