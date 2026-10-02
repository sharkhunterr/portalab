"""``/me/preferences`` facade (T015; 002 FR-013..017): user-overridable settings only, bounded by policy,
``locked`` reported; plus the erasure/export participants for user-scope values (021)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict
from portalab.modules.administration.config.registry import is_user_overridable
from portalab.modules.administration.config.resolution import MISSING
from portalab.modules.administration.config.service import Change, ConfigService


@dataclass(frozen=True, slots=True)
class PreferenceView:
    key: str
    value: Any
    source: str
    locked: bool
    user_value: Any
    user_value_retained: bool
    description: str


class UserPreferences:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    def _keys(self) -> list[str]:
        return [d.key for d in self.config.registry.all() if is_user_overridable(d) and not d.sensitive]

    async def views(self, user_id: UUID) -> list[PreferenceView]:
        views = []
        for key in self._keys():
            declaration = self.config.registry.declaration(key)
            effective = await self.config.get(key, user_id=user_id)
            own = await self.config.stored_value(key, "user", str(user_id))
            views.append(
                PreferenceView(
                    key=key,
                    value=effective.value,
                    source=effective.source,
                    locked=effective.locked,
                    user_value=None if own is MISSING else own,
                    user_value_retained=effective.user_value_retained,
                    description=declaration.description,
                )
            )
        return views

    async def set(self, principal: Principal, values: dict[str, Any]) -> list[PreferenceView]:
        assert principal.user_id is not None
        allowed = set(self._keys())
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise Conflict(
                "These settings are not personal preferences.",
                code="admin.not_a_preference",
                extensions={"keys": unknown},
            )
        changes = [
            Change(key, value, "user", str(principal.user_id), unset=value is None)
            for key, value in values.items()
        ]
        await self.config.apply(changes, principal, admin_change=False, reason="user preference")
        return await self.views(principal.user_id)


class PreferenceErasureParticipant:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.config.database.unit_of_work() as uow:
            await self.config.delete_user_values(uow.session, user_id)


class PreferenceExportContributor:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        records = []
        for declaration in self.config.registry.all():
            if not is_user_overridable(declaration) or declaration.sensitive:
                continue
            own = await self.config.stored_value(declaration.key, "user", str(user_id))
            if own is not MISSING:
                records.append(ExportRecord("preference", {"setting": declaration.key, "value": own}))
        return records
