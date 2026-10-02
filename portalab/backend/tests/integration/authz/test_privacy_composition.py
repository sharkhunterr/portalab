"""003 T031 — permissions and privacy compose: the engine allows without reading visibility, a
``VisibilityFilter`` applied after ``require()`` still hides Private data, and preferences are untouched."""

from uuid import uuid4

from sqlalchemy import text

from portalab.core.visibility_port import OwnerOnlyVisibility, Redacted
from tests.authz_fixtures import AuthzPlatform, insert_user, user


async def test_permitted_reader_still_cannot_see_private_data(platform: AuthzPlatform) -> None:
    owner, reader = await insert_user(platform.database), await insert_user(platform.database)
    assert await platform.authz.engine.is_allowed(user(reader), "users.read")  # permission: yes
    visibility = OwnerOnlyVisibility()
    hidden = await visibility.filter(user(reader), owner, "profile_field", "bio", "my private bio")
    assert isinstance(hidden, Redacted)  # privacy: still no
    assert (
        await visibility.filter(user(owner), owner, "profile_field", "bio", "my private bio")
        == "my private bio"
    )


async def test_engine_never_touches_visibility_preferences(platform: AuthzPlatform) -> None:
    owner = await insert_user(platform.database)
    async with platform.database.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO identity.profile_fields "
                "(user_id, key, value, visibility_preference, updated_at) "
                "VALUES (:u, 'bio', 'hello', 'private', now())"
            ),
            {"u": owner},
        )
    for _ in range(3):
        await platform.authz.engine.is_allowed(user(uuid4()), "users.read")
    async with platform.database.engine.connect() as conn:
        preference = (
            await conn.execute(
                text("SELECT visibility_preference FROM identity.profile_fields WHERE user_id = :u"),
                {"u": owner},
            )
        ).scalar_one()
    assert preference == "private"
