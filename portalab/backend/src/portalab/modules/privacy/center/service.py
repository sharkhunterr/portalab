"""Privacy center (T038): the inventory of datum classes held about me, their effective visibility, any
admin lock and the retention window; changing my own preference goes to the data owner's provider and is
kept (but not effective) while an admin override is active (CD-016)."""

from dataclasses import dataclass
from uuid import UUID

from portalab.capabilities.visibility import LEVELS, DatumClassRegistry, Level, default_datum_classes
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.modules.privacy.settings import PrivacyConfig
from portalab.modules.privacy.visibility.providers import PreferenceProviders
from portalab.modules.privacy.visibility.service import VisibilityService


@dataclass(frozen=True, slots=True)
class DatumEntry:
    datum_class: str
    owner: str
    classification: str
    description: str
    default_level: str
    effective_level: str
    locked_by_policy: bool
    user_choosable: bool
    retention_days: int | None


class PrivacyCenter:
    def __init__(
        self,
        visibility: VisibilityService,
        providers: PreferenceProviders,
        *,
        datum_classes: DatumClassRegistry = default_datum_classes,
        config: PrivacyConfig | None = None,
    ) -> None:
        self.visibility = visibility
        self.providers = providers
        self.datum_classes = datum_classes
        self.config = config or PrivacyConfig()

    async def inventory(self, subject: UUID) -> list[DatumEntry]:
        entries = []
        for datum in self.datum_classes.all():
            policy = await self.visibility.active_policy(subject, datum.key)
            entries.append(
                DatumEntry(
                    datum_class=datum.key,
                    owner=datum.owner,
                    classification=datum.classification,
                    description=datum.description,
                    default_level=self.visibility.default_level(datum.key),
                    effective_level=await self.visibility.effective_level(subject, datum.key, None),
                    locked_by_policy=policy is not None and policy.mode != "user_choice",
                    user_choosable=datum.user_choosable
                    and self.providers.provider_for(datum.key) is not None,
                    retention_days=self.config.retention_days.get(datum.classification),
                )
            )
        return entries

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: str
    ) -> bool:
        """Store my preference; returns whether it is effective now (False while an override applies)."""
        datum = self.datum_classes.get(datum_class)
        if datum is None:
            raise NotFound("Unknown data class.", code="privacy.unknown_datum_class")
        if level not in LEVELS:
            raise ValidationFailed("Unknown visibility level.", code="privacy.invalid_level")
        provider = self.providers.provider_for(datum_class)
        if provider is None or not datum.user_choosable:
            raise Conflict(
                "This data has no user-selectable visibility yet.", code="privacy.preference_not_supported"
            )
        typed: Level = level  # type: ignore[assignment]
        await provider.set_preference(subject, datum_class, datum_ref, typed)
        policy = await self.visibility.active_policy(subject, datum_class)
        return policy is None or policy.mode == "user_choice"
