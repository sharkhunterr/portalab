"""Effective visibility (T011; R1): **active admin policy ▸ owner preference ▸ class default**.

Policies are read at evaluation time (``ends_at`` past ⇒ no longer active), so removing or expiring an
override restores the preference automatically; the preference itself is never written here (FR-006/007).
A subject-specific policy wins over a class-wide one; ``user_choice`` exempts a subject from a class-wide
policy. Unknown classes are private.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select

from portalab.capabilities.visibility import DatumClassRegistry, Level, default_datum_classes
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.privacy.models import VisibilityPolicy
from portalab.modules.privacy.settings import PrivacyConfig
from portalab.modules.privacy.visibility.providers import PreferenceProviders


class VisibilityService:
    def __init__(
        self,
        database: Database,
        providers: PreferenceProviders,
        *,
        datum_classes: DatumClassRegistry = default_datum_classes,
        config: PrivacyConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.providers = providers
        self.datum_classes = datum_classes
        self.config = config or PrivacyConfig()
        self.clock = clock

    def default_level(self, datum_class: str) -> Level:
        configured = self.config.default_levels.get(datum_class)
        if configured is not None:
            return configured  # type: ignore[return-value]
        registered = self.datum_classes.get(datum_class)
        return registered.default_level if registered else "private"

    async def active_policy(
        self, subject: UUID, datum_class: str, now: datetime | None = None
    ) -> VisibilityPolicy | None:
        now = now or utc_now(self.clock)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(VisibilityPolicy).where(
                        VisibilityPolicy.datum_class == datum_class,
                        VisibilityPolicy.removed_at.is_(None),
                        or_(VisibilityPolicy.ends_at.is_(None), VisibilityPolicy.ends_at > now),
                        or_(
                            VisibilityPolicy.subject_user_id == subject,
                            VisibilityPolicy.subject_user_id.is_(None),
                        ),
                    )
                )
            ).scalars()
            policies = list(rows)
        specific = [policy for policy in policies if policy.subject_user_id == subject]
        if specific:
            return specific[0]
        return policies[0] if policies else None

    async def effective_level(self, subject: UUID, datum_class: str, datum_ref: str | None = None) -> Level:
        policy = await self.active_policy(subject, datum_class)
        if policy is not None and policy.mode != "user_choice" and policy.level is not None:
            return policy.level  # type: ignore[return-value]
        preference = await self.providers.preference(subject, datum_class, datum_ref)
        return preference or self.default_level(datum_class)
