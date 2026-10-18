"""The wire between Portalab and a confined plugin's process (spec 030, contracts/child-protocol.md).

One UTF-8 JSON object per line, at most :data:`MAX_LINE` bytes. Values travel through :class:`Codec`: plain
JSON, tagged datetimes, dates, UUIDs, decimals and bytes, and **dataclasses of Portalab's contracts only**
(their module under ``portalab.capabilities``, ``portalab.sdk`` or ``portalab.core.authz_port``), rebuilt
field by field — never an arbitrary class, never code. A callable or a provider object becomes a reference
(``$h``: a handler, ``$o``: an object with methods) that the other side calls back through the wire.
"""

import base64
import dataclasses
import importlib
import inspect
import json
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

MAX_LINE = 1024 * 1024
ALLOWED_MODULES = ("portalab.capabilities.", "portalab.sdk.", "portalab.core.authz_port")
MAX_DEPTH = 32


class ProtocolError(ValueError):
    """A message that cannot be read (malformed, too large, too deep, a type that is not allowed)."""


class Oversize(ProtocolError):
    pass


def encode_line(message: Mapping[str, Any]) -> bytes:
    raw = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) >= MAX_LINE:
        raise Oversize(f"message of {len(raw)} bytes")
    return raw + b"\n"


def decode_line(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_LINE:
        raise Oversize(f"message of {len(raw)} bytes")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ProtocolError("malformed message") from error
    if not isinstance(value, dict) or not isinstance(value.get("t"), str):
        raise ProtocolError("a message is an object with a type")
    return value


def _allowed(cls: type) -> bool:
    module = getattr(cls, "__module__", "")
    return any(module == m.rstrip(".") or module.startswith(m) for m in ALLOWED_MODULES)


def _class(path: str) -> type:
    module_name, _, name = path.rpartition(".")
    if not any(module_name == m.rstrip(".") or module_name.startswith(m) for m in ALLOWED_MODULES):
        raise ProtocolError(f"type {path!r} is not allowed")
    try:
        cls = getattr(importlib.import_module(module_name), name)
    except (ImportError, AttributeError) as error:
        raise ProtocolError(f"unknown type {path!r}") from error
    if not (isinstance(cls, type) and (dataclasses.is_dataclass(cls) or issubclass(cls, Enum))):
        raise ProtocolError(f"type {path!r} is not a contract")
    return cls


class Codec:
    """Encodes values for the wire; references to callables and objects go through ``refer``/``resolve``.

    ``refer(value) -> dict`` registers a local callable or object and returns its reference;
    ``resolve(ref) -> Any`` turns a remote reference into a local proxy. ``strip`` drops fields that must
    never cross (the principal's session).
    """

    def __init__(
        self,
        refer: Callable[[Any], dict[str, Any]] | None = None,
        resolve: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.refer = refer
        self.resolve = resolve

    def encode(self, value: Any, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise ProtocolError("value too deep")
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, float):
            return value if value == value and value not in (float("inf"), float("-inf")) else None
        if getattr(type(value), "__portalab_reference__", False) and self.refer is not None:
            return self.refer(value)  # an object handed on purpose (its methods called back)
        if isinstance(value, Enum) and _allowed(type(value)):
            return {"$enum": f"{type(value).__module__}.{type(value).__qualname__}", "v": value.value}
        if isinstance(value, Enum):
            return self.encode(value.value, depth + 1)
        if isinstance(value, datetime):
            return {"$dt": value.isoformat()}
        if isinstance(value, date):
            return {"$d": value.isoformat()}
        if isinstance(value, UUID):
            return {"$u": str(value)}
        if isinstance(value, Decimal):
            return {"$dec": str(value)}
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {"$b": base64.b64encode(bytes(value)).decode()}
        if isinstance(value, Mapping):
            out: dict[str, Any] = {}
            for key, item in value.items():
                out[str(key)] = self.encode(item, depth + 1)
            return {"$m": out} if any(k.startswith("$") for k in out) else out
        if isinstance(value, (list, tuple, set, frozenset)):
            items = [self.encode(item, depth + 1) for item in value]
            return {"$t": items} if isinstance(value, tuple) else items
        if dataclasses.is_dataclass(value) and not isinstance(value, type) and _allowed(type(value)):
            fields = {}
            for f in dataclasses.fields(value):
                if f.name == "session_id":  # a principal's session never crosses
                    continue
                fields[f.name] = self.encode(getattr(value, f.name), depth + 1)
            return {"$dc": f"{type(value).__module__}.{type(value).__qualname__}", "f": fields}
        if (callable(value) or _has_methods(value)) and self.refer is not None:
            return self.refer(value)
        return {"$unsupported": type(value).__name__}

    def decode(self, value: Any, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise ProtocolError("value too deep")
        if isinstance(value, list):
            return [self.decode(item, depth + 1) for item in value]
        if not isinstance(value, dict):
            return value
        if "$dt" in value:
            return datetime.fromisoformat(str(value["$dt"]))
        if "$d" in value:
            return date.fromisoformat(str(value["$d"]))
        if "$u" in value:
            return UUID(str(value["$u"]))
        if "$dec" in value:
            return Decimal(str(value["$dec"]))
        if "$b" in value:
            return base64.b64decode(str(value["$b"]))
        if "$t" in value:
            return tuple(self.decode(item, depth + 1) for item in value["$t"])
        if "$m" in value:
            return {k: self.decode(v, depth + 1) for k, v in dict(value["$m"]).items()}
        if "$enum" in value:
            return _class(str(value["$enum"]))(value.get("v"))
        if "$dc" in value:
            cls = _class(str(value["$dc"]))
            raw = value.get("f") or {}
            names = {f.name for f in dataclasses.fields(cls) if f.init}
            kwargs = {k: self.decode(v, depth + 1) for k, v in dict(raw).items() if k in names}
            try:
                return cls(**kwargs)
            except TypeError as error:
                raise ProtocolError(f"cannot rebuild {cls.__name__}") from error
        if "$h" in value or "$o" in value:
            if self.resolve is None:
                raise ProtocolError("references are not accepted here")
            return self.resolve(value)
        if "$unsupported" in value:
            return None
        return {k: self.decode(v, depth + 1) for k, v in value.items()}


def _has_methods(value: Any) -> bool:
    return any(
        not name.startswith("_") and callable(getattr(value, name, None))
        for name in dir(type(value))
        if not name.startswith("_")
    )


def describe_object(value: Any) -> tuple[list[str], list[str], dict[str, Any]]:
    """An object's public async methods, sync methods and simple attributes (for an ``$o`` reference)."""
    async_methods: list[str] = []
    sync_methods: list[str] = []
    attrs: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            item = getattr(value, name)
        except Exception:  # noqa: S112 — a property that fails is simply not described
            continue
        if inspect.iscoroutinefunction(item):
            async_methods.append(name)
        elif callable(item):
            sync_methods.append(name)
        elif item is None or isinstance(item, (bool, int, float, str, tuple, list, dict)):
            attrs[name] = item
    return async_methods, sync_methods, attrs
