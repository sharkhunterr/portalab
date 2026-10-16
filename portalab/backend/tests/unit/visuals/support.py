"""Shared helpers for the visual packs tests (spec 028): small packs, a fake shop and a fake interface
registry (UI's own validation, without its tables)."""

import io
import json
import zipfile
from collections.abc import Iterable, Mapping
from typing import Any

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict
from portalab.modules.ui.settings import BUILTIN_KEYS
from portalab.modules.ui.themes.definition import floor_report, validate_definition
from portalab.modules.visuals.store import Files


def zip_of(files: Mapping[str, bytes | str], prefix: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(prefix + name, data)
    return buffer.getvalue()


def tiny_pack(version: str = "1.0.0", pack: str = "tiny", **element: Any) -> dict[str, bytes | str]:
    base = {
        "type": "avatar_frame",
        "look": "tiny",
        "names": {"fr": "Petit", "en": "Tiny"},
        "render": {"kind": "css", "css": ["f.css"]},
        "economy": {"price": 400, "rarity": "rare"},
    }
    return {
        "pack.json": json.dumps(
            {"format": 1, "id": pack, "version": version, "names": {"fr": "T", "en": "T"}}
        ),
        "elements/frame/element.json": json.dumps({**base, **element}),
        "elements/frame/f.css": '.avatar-frame[data-frame="tiny"] { color: red; }',
    }


def files_of(files: Mapping[str, bytes | str]) -> Files:
    return Files({k: v.encode() if isinstance(v, str) else v for k, v in files.items()})


class FakeWriter:
    def __init__(self) -> None:
        self.products: dict[str, dict[str, Any]] = {}
        self.withdrawn: list[str] = []
        self.retired: list[str] = []
        self.owned: dict[str, int] = {}

    async def publish(self, actor: Principal, product: Mapping[str, Any]) -> str:
        outcome = "revised" if product["key"] in self.products else "created"
        self.products[product["key"]] = dict(product)
        if product["key"] in self.withdrawn:
            self.withdrawn.remove(product["key"])
        return outcome

    async def withdraw(self, actor: Principal, key: str) -> bool:
        on_sale = key in self.products and key not in self.withdrawn
        self.withdrawn.append(key)
        return on_sale

    async def existing(self, keys: Iterable[str]) -> frozenset[str]:
        return frozenset(k for k in keys if k in self.products)

    async def owners(self, keys: Iterable[str]) -> int:
        return sum(self.owned.get(k, 0) for k in keys)

    async def retire(self, actor: Principal, key: str) -> None:
        self.retired.append(key)


class FakeInterfaces:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def validate(self, document: Mapping[str, Any]) -> tuple[str | None, list[str], dict[str, Any] | None]:
        theme, errors = validate_definition(document)
        if theme is None:
            return None, errors, None
        return theme.key, [], dict(floor_report(theme))

    def builtin_keys(self) -> frozenset[str]:
        return frozenset(BUILTIN_KEYS)

    async def source_of(self, key: str) -> str | None:
        row = self.rows.get(key)
        return row["source"] if row else None

    async def put(self, actor: Principal, document: Mapping[str, Any], *, source: str) -> None:
        key = str(document["key"])
        if key in self.rows and self.rows[key]["source"] != source:
            raise Conflict("taken")
        theme, errors = validate_definition(document)
        assert theme is not None, errors
        self.rows[key] = {"source": source, "enabled": self.rows.get(key, {}).get("enabled", False)}

    async def set_enabled(self, actor: Principal, key: str, enabled: bool) -> None:
        if key in self.rows:
            self.rows[key]["enabled"] = enabled
