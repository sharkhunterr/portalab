"""Profile, display name and avatar (T038; FR-009..012).

Field visibility: identity stores only the user's *preference* (default ``private``). The effective
visibility engine belongs to Privacy (021); until it is wired, :func:`visible_to` applies the baseline
"default not-public" rule: the owner sees everything, other members see ``public`` and ``community`` fields
only, ``leaderboard`` fields stay out of profiles and ``private`` never leaves the owner.
"""

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.blobstore import BlobNotFound
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.jobs.queue import enqueue
from portalab.core.visibility_port import Redacted
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.display_name import clean_display_name, display_name_key
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import VISIBILITY_PREFERENCES, Profile, ProfileField, User
from portalab.modules.identity.services.account_service import is_unique_violation
from portalab.modules.identity.services.avatar import OUTPUT_CONTENT_TYPE, normalize_avatar
from portalab.modules.identity.services.common import DisplayNameTaken, UserNotFound, publish
from portalab.modules.identity.services.visibility import PROFILE_FIELD

FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_FIELDS = 20
MAX_VALUE_LENGTH = 1000
AVATAR_GC_JOB = "identity.avatar_blob_gc"
AVATAR_NAMESPACE = "avatars"


@dataclass(frozen=True, slots=True)
class FieldUpdate:
    value: str | None
    visibility: str = "private"


@dataclass(frozen=True, slots=True)
class FieldView:
    key: str
    value: str | None
    visibility: str


@dataclass(frozen=True, slots=True)
class ProfileView:
    user_id: UUID
    display_name: str | None
    has_avatar: bool
    fields: list[FieldView]


def visible_to(visibility: str, *, viewer_is_owner: bool) -> bool:
    return viewer_is_owner or visibility in ("public", "community")


class ProfileService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def _live_user(self, session: AsyncSession, user_id: UUID) -> User:
        user = await session.get(User, user_id, with_for_update=True)
        if user is None or user.state == AccountState.DELETED.value:
            raise UserNotFound()
        return user

    async def update(
        self,
        principal: Principal,
        *,
        display_name: str | None = None,
        fields: Mapping[str, FieldUpdate] | None = None,
    ) -> ProfileView:
        if principal.user_id is None:
            raise UserNotFound()
        user_id = principal.user_id
        now = self.ctx.now()
        changed: list[str] = []
        for key, update in (fields or {}).items():
            if not FIELD_KEY.fullmatch(key):
                raise ValidationFailed("Invalid profile field name.", code="user.profile_field_invalid")
            if update.visibility not in VISIBILITY_PREFERENCES:
                raise ValidationFailed("Unknown visibility.", code="user.profile_visibility_invalid")
            if update.value is not None and len(update.value) > MAX_VALUE_LENGTH:
                raise ValidationFailed(
                    "A profile field is limited to 1000 characters.", code="user.profile_field_invalid"
                )
        async with self.ctx.database.unit_of_work() as uow:
            session = uow.session
            user = await self._live_user(session, user_id)
            if display_name is not None and clean_display_name(display_name) != user.display_name:
                user.display_name = clean_display_name(display_name)
                user.display_name_key = display_name_key(display_name)
                user.updated_at = now
                try:
                    async with session.begin_nested():
                        await session.flush()
                except IntegrityError as exc:
                    if is_unique_violation(exc, "uq_users_display_name_key"):
                        raise DisplayNameTaken() from exc
                    raise
                changed.append("display_name")
            for key, update in (fields or {}).items():
                if update.value is None:
                    await session.execute(
                        delete(ProfileField).where(ProfileField.user_id == user_id, ProfileField.key == key)
                    )
                else:
                    await session.merge(
                        ProfileField(
                            user_id=user_id,
                            key=key,
                            value=update.value,
                            visibility_preference=update.visibility,
                            updated_at=now,
                        )
                    )
                changed.append(f"field:{key}")
            await session.flush()
            count = await session.scalar(
                select(func.count()).select_from(ProfileField).where(ProfileField.user_id == user_id)
            )
            if (count or 0) > MAX_FIELDS:
                raise ValidationFailed(
                    f"A profile has at most {MAX_FIELDS} fields.", code="user.profile_too_many_fields"
                )
            if changed:
                await publish(
                    self.ctx,
                    session,
                    "user.profile_updated",
                    user_id,
                    actor=principal,
                    occurred_at=now,
                    metadata={"changed": sorted(changed)},
                )
            return await self._view(session, user_id, viewer=principal)

    async def view(self, viewer: Principal, user_id: UUID) -> ProfileView:
        async with self.ctx.database.session() as session:
            user = await session.get(User, user_id)
            if user is None or user.state == AccountState.DELETED.value:
                raise UserNotFound()
            return await self._view(session, user_id, viewer=viewer)

    async def _view(self, session: AsyncSession, user_id: UUID, *, viewer: Principal) -> ProfileView:
        user = await session.get(User, user_id)
        profile = await session.get(Profile, user_id)
        rows = (
            await session.execute(
                select(ProfileField).where(ProfileField.user_id == user_id).order_by(ProfileField.key)
            )
        ).scalars()
        fields = []
        for row in rows:
            if await self._shown(viewer, user_id, row):
                fields.append(FieldView(row.key, row.value, row.visibility_preference))
        return ProfileView(
            user_id=user_id,
            display_name=user.display_name if user else None,
            has_avatar=bool(profile and profile.avatar_blob_key),
            fields=fields,
        )

    async def _shown(self, viewer: Principal, owner: UUID, row: ProfileField) -> bool:
        """Visibility is decided by the privacy engine (021) when installed, else by the baseline rule."""
        if self.ctx.visibility is None:
            return visible_to(row.visibility_preference, viewer_is_owner=viewer.user_id == owner)
        shown = await self.ctx.visibility.filter(viewer, owner, PROFILE_FIELD, row.key, row.value)
        return not isinstance(shown, Redacted)

    # --- avatar --------------------------------------------------------------------------------------
    async def set_avatar(self, principal: Principal, data: bytes) -> None:
        if principal.user_id is None:
            raise UserNotFound()
        # 422 before anything changes: the old avatar is kept (#274: decoded off the event loop)
        normalized = await asyncio.to_thread(normalize_avatar, data)
        blob = await self.ctx.blobs.put(AVATAR_NAMESPACE, normalized, content_type=OUTPUT_CONTENT_TYPE)
        await self._replace(principal, blob.key, OUTPUT_CONTENT_TYPE)

    async def remove_avatar(self, principal: Principal) -> None:
        await self._replace(principal, None, None)

    async def _replace(self, principal: Principal, key: str | None, content_type: str | None) -> None:
        assert principal.user_id is not None
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await self._live_user(uow.session, principal.user_id)
            profile = await uow.session.get(Profile, principal.user_id, with_for_update=True)
            if profile is None:
                profile = Profile(user_id=principal.user_id, updated_at=now)
                uow.session.add(profile)
            previous = profile.avatar_blob_key
            profile.avatar_blob_key = key
            profile.avatar_content_type = content_type
            profile.updated_at = now
            if previous and previous != key:
                await schedule_blob_gc(uow.session, previous, self.ctx)
            await publish(
                self.ctx,
                uow.session,
                "user.profile_updated",
                principal.user_id,
                actor=principal,
                occurred_at=now,
                metadata={"changed": ["avatar"]},
            )

    async def avatar(self, user_id: UUID) -> tuple[str, str]:
        async with self.ctx.database.session() as session:
            user = await session.get(User, user_id)
            profile = await session.get(Profile, user_id)
        if (
            user is None
            or user.state == AccountState.DELETED.value
            or profile is None
            or not profile.avatar_blob_key
        ):
            raise NotFound()
        return profile.avatar_blob_key, profile.avatar_content_type or OUTPUT_CONTENT_TYPE


async def schedule_blob_gc(session: AsyncSession, key: str, ctx: IdentityContext) -> None:
    await enqueue(
        session,
        kind=AVATAR_GC_JOB,
        payload={"blob": key},  # idempotent: deleting an absent or re-referenced blob is a no-op
        clock=ctx.clock,
    )


async def collect_avatar_blob(ctx: IdentityContext, key: str) -> bool:
    """Delete an avatar blob unless a profile references it again (content-addressed keys can be shared)."""
    async with ctx.database.session() as session:
        referenced = await session.scalar(
            select(func.count()).select_from(Profile).where(Profile.avatar_blob_key == key)
        )
    if referenced:
        return False
    try:
        return await ctx.blobs.delete(key)
    except BlobNotFound:
        return False
