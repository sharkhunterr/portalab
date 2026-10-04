"""Setting registry (T007): the kernel declarations (``declare_setting``) made persistent and serveable.

Adds what the store needs on top of the 001 catalog: allowed scopes per key, stored-value upgrades
(``SettingUpgrade``), dynamic validators (e.g. widget keys known only at runtime, F18) and plugin-manifest
settings — all owner-tagged so ``unregister(owner)`` removes a plugin's contributions (F20).
"""

from collections.abc import Iterable, Mapping
from typing import Any

from portalab.capabilities.administration import DynamicValidator, UserDynamicValidator
from portalab.capabilities.config import SettingUpgrade
from portalab.core.config_declaration import SettingCatalog, SettingDeclaration, default_catalog
from portalab.core.errors import NotFound

_SCHEMAS: dict[str, Any] = {
    "bool": bool,
    "int": int,
    "float": float,
    "string": str,
    "list": list,
    "object": dict,
}


class UnknownSetting(NotFound):
    default_code = "admin.unknown_setting"
    default_title = "Unknown setting"


def allowed_scopes(declaration: SettingDeclaration) -> set[str]:
    scopes = {"global"}
    if declaration.scope in ("module", "plugin"):
        scopes.add(declaration.scope)
    if declaration.scope == "user" or declaration.user_overridable:
        scopes.add("user")
    return scopes


def is_user_overridable(declaration: SettingDeclaration) -> bool:
    return declaration.scope == "user" or declaration.user_overridable


class SettingRegistry:
    def __init__(self, catalog: SettingCatalog = default_catalog) -> None:
        self.catalog = catalog
        self._upgrades: dict[tuple[str, int], tuple[SettingUpgrade, str]] = {}
        self._validators: dict[str, tuple[DynamicValidator, str]] = {}
        self._user_validators: dict[str, tuple[UserDynamicValidator, str]] = {}

    def declaration(self, key: str) -> SettingDeclaration:
        for declaration in self.catalog.all():
            if declaration.key == key:
                return declaration
        raise UnknownSetting(f"No setting is declared as {key!r}.")

    def all(self) -> list[SettingDeclaration]:
        return self.catalog.all()

    def register_upgrade(self, upgrade: SettingUpgrade, *, owner: str = "core") -> None:
        slot = (upgrade.key, upgrade.from_version)
        if slot in self._upgrades:
            raise ValueError(f"an upgrade from version {upgrade.from_version} of {upgrade.key!r} exists")
        self._upgrades[slot] = (upgrade, owner)

    def upgrade(self, key: str, value: Any, stored_version: int, target_version: int) -> Any:
        """Upgrade a stored value step by step; raises when a step is missing (never a silent reset)."""
        for version in range(stored_version, target_version):
            entry = self._upgrades.get((key, version))
            if entry is None:
                raise LookupError(f"no upgrade for {key!r} from version {version}")
            value = entry[0].upgrade(value)
        return value

    def register_validator(self, key: str, validator: DynamicValidator, *, owner: str) -> None:
        self._validators[key] = (validator, owner)

    def register_user_validator(self, key: str, validator: UserDynamicValidator, *, owner: str) -> None:
        """A validator that also receives the user a ``user``-scope value is written for (``None`` for
        other scopes) — 027 US11: a theme sold in the Marketplace may only be chosen by its owners."""
        self._user_validators[key] = (validator, owner)

    async def dynamic_errors(self, key: str, value: Any, *, user_ref: str | None = None) -> list[str]:
        errors: list[str] = []
        if (entry := self._validators.get(key)) is not None:
            errors += await entry[0](value)
        if (user_entry := self._user_validators.get(key)) is not None:
            errors += await user_entry[0](value, user_ref)
        return errors

    def declare_plugin_settings(self, plugin_id: str, settings: Iterable[Mapping[str, Any]]) -> list[str]:
        """Plugin-scope settings from a plugin manifest (F18): ``{key, type, default, description,
        user_overridable?}``; keys are namespaced ``plugin_<id>.<name>``."""
        owner = f"plugin:{plugin_id}"
        prefix = f"plugin_{plugin_id.replace('-', '_')}."
        keys = []
        for entry in settings:
            name = str(entry["key"])
            key = name if name.startswith(prefix) else prefix + name
            schema = _SCHEMAS.get(str(entry.get("type", "string")))
            if schema is None:
                raise ValueError(f"unsupported setting type {entry.get('type')!r}")
            self.catalog.declare(
                scope="plugin",
                key=key,
                schema=schema,
                default=entry.get("default"),
                user_overridable=bool(entry.get("user_overridable", False)),
                owner=owner,
                description=str(entry.get("description", "")),
            )
            keys.append(key)
        return keys

    def unregister(self, owner: str) -> int:
        removed = self.catalog.unregister(owner)
        for slot in [slot for slot, (_, who) in self._upgrades.items() if who == owner]:
            del self._upgrades[slot]
            removed += 1
        for key in [key for key, (_, who) in self._validators.items() if who == owner]:
            del self._validators[key]
            removed += 1
        for key in [key for key, (_, who) in self._user_validators.items() if who == owner]:
            del self._user_validators[key]
            removed += 1
        return removed
