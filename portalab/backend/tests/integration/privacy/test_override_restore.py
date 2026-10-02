"""021 T012 — admin override: preference untouched while forced; changed preference stored but not
effective; removal restores automatically; expiry restores; no stacking; both actions audited."""

from datetime import timedelta
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select, text

from portalab.core.time import FixedClock
from portalab.modules.authz.models import AuditEntry
from portalab.modules.privacy.policies.service import PolicyRequest
from tests.authz_fixtures import make_admin, user
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


async def _preference_row(full: FullPlatform, owner: UUID) -> tuple[object, ...]:
    async with full.database.engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT value, visibility_preference FROM identity.profile_fields "
                    "WHERE user_id = :u AND key = 'bio'"
                ),
                {"u": owner},
            )
        ).one()
    return tuple(row)


async def test_override_preserves_and_restores(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform, clock: FixedClock
) -> None:
    owner = await create_user(module_of(app), "owner")
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await login(client, "owner")
    await client.patch(
        "/api/v1/me/profile", json={"fields": {"bio": {"value": "hello", "visibility": "public"}}}
    )
    before = await _preference_row(full, owner)
    level = full.privacy.visibility.effective_level

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        applied = await boss.post(
            "/api/v1/privacy/policies",
            json={
                "datum_class": "profile_field",
                "mode": "force_private",
                "subject_user_id": str(owner),
                "reason": "abuse",
            },
        )
        assert applied.status_code == 201
        assert await level(owner, "profile_field", "bio") == "private"
        assert await _preference_row(full, owner) == before  # byte-identical preference

        stacked = await boss.post(
            "/api/v1/privacy/policies",
            json={
                "datum_class": "profile_field",
                "mode": "force_visible",
                "level": "public",
                "subject_user_id": str(owner),
                "reason": "again",
            },
        )
        assert stacked.status_code == 409 and stacked.json()["code"] == "privacy.policy_exists"

        # the user changes the preference during the override: stored, not effective
        changed = await client.put(
            "/api/v1/me/privacy/visibility/profile_field", json={"level": "community", "datum_ref": "bio"}
        )
        assert changed.status_code == 200 and changed.json() == {"stored": True, "effective_now": False}
        assert await level(owner, "profile_field", "bio") == "private"

        removed = await boss.delete(f"/api/v1/privacy/policies/{applied.json()['id']}")
        assert removed.status_code == 204
    assert await level(owner, "profile_field", "bio") == "community"  # automatic restore

    async with full.database.session() as session:
        actions = list((await session.execute(select(AuditEntry.action))).scalars())
    assert "privacy.override_applied" in actions and "privacy.override_removed" in actions


async def test_expiring_override_and_class_wide_policy(full: FullPlatform, clock: FixedClock) -> None:
    from tests.authz_fixtures import insert_user

    owner, other = await insert_user(full.database), await insert_user(full.database)
    admin = user(await insert_user(full.database))
    policies = full.privacy.policies
    level = full.privacy.visibility.effective_level
    await policies.apply(
        admin,
        PolicyRequest(
            "profile_field",
            "force_private",
            "temporary",
            subject_user_id=owner,
            ends_at=clock.now() + timedelta(hours=1),
        ),
    )
    assert await level(owner, "profile_field", None) == "private"
    clock.advance(timedelta(hours=2))
    await policies.apply(
        admin, PolicyRequest("profile_field", "force_visible", "class-wide", level="community")
    )
    assert await level(other, "profile_field", None) == "community"  # class-wide policy
    await policies.apply(
        admin, PolicyRequest("profile_field", "user_choice", "exempt", subject_user_id=owner)
    )
    assert await level(owner, "profile_field", None) == "private"  # exempt ⇒ preference/default again
