"""Visibility contracts (spec 021): datum-class registry and ``privacy.visibility_preference`` providers.

Data owners register the classes of personal data they hold (``register_datum_class``) and, when users can
choose a visibility for them, provide a ``VisibilityPreferenceProvider`` (the preference stays with its
owner: no second preference store, R2). Privacy (021) resolves the effective level as
**active admin policy ▸ owner preference ▸ class default** and never writes preferences under an override.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, get_args, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

Level = Literal["public", "community", "leaderboard", "private"]
LEVELS: tuple[str, ...] = get_args(Level)
DataClass = Literal["personal", "activity", "technical", "history", "audit", "aggregate"]
DATA_CLASSES: tuple[str, ...] = get_args(DataClass)

PREFERENCE_CAPABILITY = "privacy.visibility_preference"


class DatumClassError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DatumClass:
    key: str
    owner: str
    default_level: Level
    classification: DataClass
    description: str = ""
    user_choosable: bool = True


class DatumClassRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, DatumClass] = {}

    def register(
        self,
        key: str,
        *,
        owner: str,
        default_level: Level = "private",
        classification: DataClass = "personal",
        description: str = "",
        user_choosable: bool = True,
    ) -> DatumClass:
        if default_level not in LEVELS:
            raise DatumClassError(f"unknown visibility level {default_level!r}")
        if classification not in DATA_CLASSES:
            raise DatumClassError(f"unknown data class {classification!r}")
        if classification in ("history", "audit", "activity") and default_level == "public":
            raise DatumClassError("historized data is never public by default (FR-010, CD-016)")
        datum = DatumClass(key, owner, default_level, classification, description, user_choosable)
        existing = self._classes.get(key)
        if existing is not None and existing != datum:
            raise DatumClassError(f"datum class {key!r} is already registered differently")
        self._classes[key] = datum
        return datum

    def get(self, key: str) -> DatumClass | None:
        return self._classes.get(key)

    def all(self) -> list[DatumClass]:
        return [self._classes[key] for key in sorted(self._classes)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, datum in self._classes.items() if datum.owner == owner]
        for key in doomed:
            del self._classes[key]
        return len(doomed)


default_datum_classes = DatumClassRegistry()
register_datum_class: Callable[..., DatumClass] = default_datum_classes.register


@runtime_checkable
class VisibilityPreferenceProvider(Protocol):
    """Implemented by the data owner for the datum classes it handles (``metadata["datum_classes"]``)."""

    async def get_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None
    ) -> Level | None: ...

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: Level
    ) -> None: ...


PREFERENCE_SPEC = CapabilitySpec(
    name=PREFERENCE_CAPABILITY,
    version="1.0",
    protocol=VisibilityPreferenceProvider,
    multi_provider=True,
    description="Owner-held visibility preferences per datum class.",
)
