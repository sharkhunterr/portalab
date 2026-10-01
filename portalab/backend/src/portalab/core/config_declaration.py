"""Setting declarations — the contract modules use to *declare* configuration (CD-011).

This is **declaration only**: no persistence and no hierarchy resolution. Administration (spec 020) owns the
configuration store, resolves Global → Module → Plugin → User, applies admin policies and audits changes.
Until then modules rely on their declared defaults.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from pydantic import TypeAdapter, ValidationError

Scope = Literal["global", "module", "plugin", "user"]
SCOPES: tuple[str, ...] = get_args(Scope)

_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")


class SettingDeclarationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SettingDeclaration:
    key: str
    scope: Scope
    schema: Any
    default: Any = field(repr=False)
    user_overridable: bool = False
    sensitive: bool = False
    version: int = 1
    owner: str = "core"
    description: str = ""
    adapter: TypeAdapter[Any] = field(repr=False, compare=False, default=TypeAdapter(object))

    def validate(self, value: Any) -> Any:
        try:
            return self.adapter.validate_python(value)
        except ValidationError as exc:
            raise SettingDeclarationError(f"invalid value for {self.key}") from exc


class SettingCatalog:
    def __init__(self) -> None:
        self._declarations: dict[str, SettingDeclaration] = {}

    def declare(
        self,
        *,
        scope: Scope,
        key: str,
        schema: Any,
        default: Any,
        user_overridable: bool = False,
        sensitive: bool = False,
        version: int = 1,
        owner: str = "core",
        description: str = "",
    ) -> SettingDeclaration:
        if scope not in SCOPES:
            raise SettingDeclarationError(f"unknown scope {scope!r}; expected one of {SCOPES}")
        if not _KEY.fullmatch(key):
            raise SettingDeclarationError(f"setting key {key!r} must look like '<module>.<name>'")
        if key in self._declarations:
            raise SettingDeclarationError(f"setting {key!r} is already declared")
        if version < 1:
            raise SettingDeclarationError("version must be >= 1")
        if sensitive and default is not None:
            raise SettingDeclarationError(f"sensitive setting {key!r} cannot have a default value")
        if sensitive and user_overridable:
            raise SettingDeclarationError(f"sensitive setting {key!r} cannot be user-overridable")
        adapter: TypeAdapter[Any] = TypeAdapter(schema)
        if default is not None:
            try:
                default = adapter.validate_python(default)
            except ValidationError as exc:
                raise SettingDeclarationError(f"default of {key!r} does not match its schema") from exc
        declaration = SettingDeclaration(
            key=key,
            scope=scope,
            schema=schema,
            default=default,
            user_overridable=user_overridable,
            sensitive=sensitive,
            version=version,
            owner=owner,
            description=description,
            adapter=adapter,
        )
        self._declarations[key] = declaration
        return declaration

    def get(self, key: str) -> SettingDeclaration:
        try:
            return self._declarations[key]
        except KeyError as exc:
            raise SettingDeclarationError(f"setting {key!r} is not declared") from exc

    def validate(self, key: str, value: Any) -> Any:
        return self.get(key).validate(value)

    def all(self) -> list[SettingDeclaration]:
        return [self._declarations[key] for key in sorted(self._declarations)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, decl in self._declarations.items() if decl.owner == owner]
        for key in doomed:
            del self._declarations[key]
        return len(doomed)


default_catalog = SettingCatalog()

declare_setting: Callable[..., SettingDeclaration] = default_catalog.declare
"""Module-level shortcut: ``declare_setting(scope=…, key=…, schema=…, default=…)``."""
