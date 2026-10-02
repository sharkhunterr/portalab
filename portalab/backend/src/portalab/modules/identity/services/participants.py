"""Identity's own privacy participants (T044).

Erasure removes what identity holds beyond the tombstoned ``users`` row: credentials, sessions, verification
tokens, profile fields, onboarding progress, avatar blob and export bundles. The append-only state history is
kept (it only references the pseudonymous id). Export returns the account, profile, onboarding, sessions
summary and state history — never credentials or token hashes.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import (
    ERASURE_CAPABILITY,
    EXPORT_CAPABILITY,
    ErasureMode,
    ExportRecord,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.identity.context import OWNER, IdentityContext
from portalab.modules.identity.models import (
    AccountStateHistory,
    Credential,
    OnboardingProgress,
    Profile,
    ProfileField,
    User,
    UserSession,
    VerificationToken,
)
from portalab.modules.identity.services.export import ExportService
from portalab.modules.identity.services.profile import collect_avatar_blob

INSTANCE_REF = "identity"


class IdentityErasureParticipant:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            session = uow.session
            for model in (Credential, UserSession, VerificationToken, ProfileField, OnboardingProgress):
                await session.execute(delete(model).where(model.user_id == user_id))
            profile = await session.get(Profile, user_id, with_for_update=True)
            avatar_key = profile.avatar_blob_key if profile else None
            if profile is not None:
                profile.avatar_blob_key = None
                profile.avatar_content_type = None
        if avatar_key:
            await collect_avatar_blob(self.ctx, avatar_key)
        await ExportService(self.ctx).delete_all_for(user_id)


class IdentityExportContributor:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        records: list[ExportRecord] = []
        async with self.ctx.database.session() as session:
            user = await session.get(User, user_id)
            if user is None:
                return records
            records.append(
                ExportRecord(
                    "account",
                    {
                        "id": str(user.id),
                        "login": user.login_display,
                        "display_name": user.display_name,
                        "email": user.email,
                        "state": user.state,
                        "created_at": user.created_at,
                        "verified_at": user.verified_at,
                        "last_sign_in_at": user.last_sign_in_at,
                    },
                )
            )
            profile = await session.get(Profile, user_id)
            records.append(ExportRecord("avatar", {"present": bool(profile and profile.avatar_blob_key)}))
            for row in (
                await session.execute(select(ProfileField).where(ProfileField.user_id == user_id))
            ).scalars():
                records.append(
                    ExportRecord(
                        "profile_field",
                        {"field": row.key, "value": row.value, "visibility": row.visibility_preference},
                    )
                )
            for step in (
                await session.execute(select(OnboardingProgress).where(OnboardingProgress.user_id == user_id))
            ).scalars():
                records.append(
                    ExportRecord("onboarding", {"step": step.step, "completed_at": step.completed_at})
                )
            for item in (
                await session.execute(select(UserSession).where(UserSession.user_id == user_id))
            ).scalars():
                records.append(
                    ExportRecord(
                        "session",
                        {
                            "created_at": item.created_at,
                            "last_seen_at": item.last_seen_at,
                            "revoked_at": item.revoked_at,
                            "client": item.user_agent_summary,
                            "network": item.ip_prefix,
                        },
                    )
                )
            history = await session.execute(
                select(AccountStateHistory)
                .where(AccountStateHistory.user_id == user_id)
                .order_by(AccountStateHistory.transition_seq)
            )
            for entry in history.scalars():
                records.append(
                    ExportRecord(
                        "account_state_history",
                        {
                            "from_state": entry.from_state,
                            "to_state": entry.to_state,
                            "reason": entry.reason,
                            "occurred_at": entry.occurred_at,
                        },
                    )
                )
        return records


def register_participants(registry: CapabilityRegistry, ctx: IdentityContext) -> None:
    registry.provide(
        ERASURE_CAPABILITY, IdentityErasureParticipant(ctx), instance_ref=INSTANCE_REF, owner=OWNER
    )
    registry.provide(
        EXPORT_CAPABILITY, IdentityExportContributor(ctx), instance_ref=INSTANCE_REF, owner=OWNER
    )
