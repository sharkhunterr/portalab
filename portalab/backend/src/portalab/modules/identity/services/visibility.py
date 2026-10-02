"""Identity's visibility contributions (spec 021 R2): the ``profile_field`` datum class and the provider of
its owner-held preference (``identity.profile_fields.visibility_preference``)."""

from typing import cast
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visibility import PREFERENCE_CAPABILITY, Level, register_datum_class
from portalab.core.errors import NotFound
from portalab.modules.identity.context import OWNER, IdentityContext
from portalab.modules.identity.models import ProfileField

PROFILE_FIELD = "profile_field"

register_datum_class(
    PROFILE_FIELD,
    owner=OWNER,
    default_level="private",
    classification="personal",
    description="Optional profile fields (bio, city, …)",
)


class ProfileFieldPreferences:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def get_preference(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level | None:
        if datum_class != PROFILE_FIELD or datum_ref is None:
            return None
        async with self.ctx.database.session() as session:
            level = await session.scalar(
                select(ProfileField.visibility_preference).where(
                    ProfileField.user_id == subject, ProfileField.key == datum_ref
                )
            )
        return cast(Level | None, level)

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: Level
    ) -> None:
        if datum_class != PROFILE_FIELD or datum_ref is None:
            raise NotFound("Choose a profile field.", code="privacy.datum_not_found")
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(ProfileField, (subject, datum_ref), with_for_update=True)
            if row is None:
                raise NotFound("This profile field does not exist.", code="privacy.datum_not_found")
            row.visibility_preference = level
            row.updated_at = self.ctx.now()


def register_visibility(registry: CapabilityRegistry, ctx: IdentityContext) -> None:
    registry.provide(
        PREFERENCE_CAPABILITY,
        ProfileFieldPreferences(ctx),
        instance_ref="identity.profile_field",
        owner=OWNER,
        metadata={"datum_classes": [PROFILE_FIELD]},
    )
