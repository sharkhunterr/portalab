"""``ui.interface_registry`` (028): the interfaces visual packs bring, validated and registered in UI's own
theme registry — the ``visuals`` module never reaches the themes' tables."""

from collections.abc import Mapping
from typing import Any

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound
from portalab.modules.ui.settings import BUILTIN_KEYS
from portalab.modules.ui.themes.definition import floor_report, validate_definition
from portalab.modules.ui.themes.service import ThemeService


class PackInterfaces:
    def __init__(self, themes: ThemeService) -> None:
        self.themes = themes

    def validate(self, document: Mapping[str, Any]) -> tuple[str | None, list[str], dict[str, Any] | None]:
        theme, errors = validate_definition(document)
        if theme is None:
            return None, errors, None
        return theme.key, [], dict(floor_report(theme))

    def builtin_keys(self) -> frozenset[str]:
        return frozenset(BUILTIN_KEYS)

    async def source_of(self, key: str) -> str | None:
        try:
            return str((await self.themes.get(key)).source)
        except NotFound:
            return None

    async def put(self, actor: Principal, document: Mapping[str, Any], *, source: str) -> None:
        key = str(document.get("key", ""))
        current = await self.source_of(key)
        if current is None:
            await self.themes.register(actor, document, source=source, owner=source)
        elif current == "builtin" and source.startswith("visuals:portalab-") and key in BUILTIN_KEYS:
            # 028: seeded by the migrations, taken over by the Portalab pack holding it
            await self.themes.adopt(actor, key, document, source=source)
        elif current == source:
            await self.themes.update(actor, key, definition=document)
        else:
            raise Conflict(f"An interface « {key} » already exists outside this pack.")

    async def set_enabled(self, actor: Principal, key: str, enabled: bool) -> None:
        try:
            await self.themes.update(actor, key, enabled=enabled)
        except NotFound:
            return
