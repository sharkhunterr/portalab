"""A confined plugin's process (spec 030, R1-R3): ``python -I -m portalab.sdk.confined.child``.

It reads its setup, **confines itself** (``portalab.core.confinement``) before any plugin code is imported,
then runs the plugin's ``register(ctx)`` with a recording context, sends what was registered, and serves
Portalab's calls. It talks only through the pipes it was started with: the protocol keeps private copies of
descriptors 0 and 1; the plugin's own ``print`` and logs go to stderr, which Portalab reads and bounds.
"""

import asyncio
import contextvars
import importlib
import inspect
import itertools
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from portalab.sdk.confined.protocol import (
    MAX_LINE,
    Codec,
    ProtocolError,
    decode_line,
    describe_object,
    encode_line,
)

CURRENT_CALL: contextvars.ContextVar[int | None] = contextvars.ContextVar("portalab_call", default=None)

# Imported before confinement, so nothing of Python's own needs loading afterwards.
PRELOAD = (
    "asyncio", "base64", "collections", "dataclasses", "datetime", "decimal", "enum", "functools",
    "hashlib", "hmac", "html", "itertools", "json", "math", "random", "re", "secrets", "statistics",
    "string", "textwrap", "typing", "unicodedata", "urllib.parse", "uuid", "zoneinfo", "portalab.sdk",
    "portalab.sdk.pages", "portalab.sdk.confined.recording",
)  # fmt: skip


class Child:
    def __init__(self, reader: Any, writer: Any) -> None:
        self.out = writer
        self.inp = reader
        self.handlers: dict[int, Any] = {}
        self.ids = itertools.count(1)
        self.asks: dict[int, asyncio.Future[Any]] = {}
        self.ask_ids = itertools.count(1)
        self.codec = Codec(refer=self.refer, resolve=self.resolve)
        self.tasks: set[asyncio.Task[Any]] = set()

    # --- references -------------------------------------------------------------------------------------
    def refer(self, value: Any) -> dict[str, Any]:
        hid = next(self.ids)
        self.handlers[hid] = value
        if inspect.isfunction(value) or inspect.ismethod(value) or inspect.iscoroutinefunction(value):
            return {"$h": hid}
        if callable(value) and not _is_object(value):
            return {"$h": hid}
        methods, sync, attrs = describe_object(value)
        values: dict[str, Any] = {}
        for name in sync:  # a sync method without arguments is evaluated now (e.g. a provider's facets())
            item = getattr(value, name)
            try:
                if not _needs_arguments(item):
                    values[name] = self.codec.encode(item())
            except Exception:  # noqa: S112 — not evaluable now: simply not offered
                continue
        return {"$o": hid, "methods": methods, "values": values, "attrs": self.codec.encode(attrs)}

    def resolve(self, ref: dict[str, Any]) -> Any:
        return ParentObject(self, ref)

    # --- wire -------------------------------------------------------------------------------------------
    def send(self, message: dict[str, Any]) -> None:
        self.out.write(encode_line(message))
        self.out.flush()

    async def ask(self, cap: str, args: dict[str, Any]) -> Any:
        from portalab.sdk.confined.recording import Denied

        aid = next(self.ask_ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self.asks[aid] = future
        message = {"t": "ask", "id": aid, "cap": cap, "args": self.codec.encode(args)}
        if (cid := CURRENT_CALL.get()) is not None:
            message["cid"] = cid  # the call it serves: Portalab acts for that call's member only
        self.send(message)
        answer = await future
        if not answer.get("ok"):
            error = answer.get("error") or {}
            raise Denied(str(error.get("code", "denied")), str(error.get("message", "refused")))
        return self.codec.decode(answer.get("value"))

    async def handle_call(self, message: dict[str, Any]) -> None:
        cid = message.get("id")
        CURRENT_CALL.set(int(cid) if isinstance(cid, int) else None)
        try:
            target = self.handlers[int(message["hid"])]
            method = message.get("method")
            if method:
                allowed, _sync, _attrs = describe_object(target)
                if method not in allowed:
                    raise LookupError(f"no method {method!r}")
                target = getattr(target, method)
            args = self.codec.decode(message.get("args") or [])
            kwargs = self.codec.decode(message.get("kwargs") or {})
            result = target(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            self.send({"t": "result", "id": cid, "ok": True, "value": self.codec.encode(result)})
        except Exception as error:
            logging.getLogger("plugin").warning(
                "call failed: %s", "".join(traceback.format_exception(error))[-2000:]
            )
            self.send(
                {
                    "t": "result",
                    "id": cid,
                    "ok": False,
                    "error": {"type": type(error).__name__, "message": str(error)[:300]},
                }
            )

    async def serve(self) -> None:
        while True:
            try:
                raw = await self.inp.readline()
            except (asyncio.LimitOverrunError, ValueError):
                os._exit(4)
            if not raw:
                os._exit(0)  # Portalab closed the pipe
            try:
                message = decode_line(raw)
            except ProtocolError:
                continue
            kind = message["t"]
            if kind == "call":
                task = asyncio.create_task(self.handle_call(message))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)
            elif kind == "answer":
                future = self.asks.pop(int(message.get("id", 0)), None)
                if future is not None and not future.done():
                    future.set_result(message)
            elif kind == "ping":
                self.send({"t": "pong", "n": message.get("n")})
            elif kind == "stop":
                os._exit(0)


class ParentObject:
    """An object of Portalab's handed to a call (e.g. an event consumer's context): its simple attributes,
    and its async methods called back through the wire."""

    def __init__(self, child: Child, ref: dict[str, Any]) -> None:
        self._child = child
        self._ref = ref
        for name, value in dict(child.codec.decode(ref.get("attrs") or {})).items():
            setattr(self, name, value)
        for name in ref.get("methods") or []:
            setattr(self, name, self._method(str(name)))

    def _method(self, name: str) -> Any:
        async def call(*args: Any, **kwargs: Any) -> Any:
            return await self._child.ask(
                "callback",
                {"oid": self._ref["$o"], "method": name, "args": list(args), "kwargs": kwargs},
            )

        return call


def _is_object(value: Any) -> bool:
    return not (inspect.isfunction(value) or inspect.ismethod(value) or inspect.isbuiltin(value))


def _needs_arguments(method: Any) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return True
    return any(
        p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        for p in signature.parameters.values()
    )


def _protocol_streams() -> tuple[Any, Any]:
    """Private copies of 0 and 1 for the protocol; 0 becomes /dev/null and 1 goes to stderr."""
    proto_in = os.fdopen(os.dup(0), "rb", buffering=0)
    proto_out = os.fdopen(os.dup(1), "wb", buffering=0)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return proto_in, proto_out


async def _main(proto_in: Any, proto_out: Any) -> None:
    from portalab.core.confinement import ConfinementError, confine
    from portalab.sdk.confined.recording import RecordingContext

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_LINE + 1)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), proto_in)
    child = Child(reader, proto_out)
    hello = decode_line(await reader.readline())
    setup = hello.get("setup") or {}
    for name in PRELOAD:
        try:
            importlib.import_module(name)
        except ImportError:
            continue
    package = Path(str(setup["package"]))
    try:
        applied = confine(
            read=[Path(p) for p in setup.get("read", [])] + [package],
            scratch=Path(str(setup["scratch"])),
            memory_mb=int(setup.get("memory_mb", 384)),
            weak=bool(setup.get("weak", False)),
        )
    except ConfinementError as error:
        child.send({"t": "confined", "ok": False, "error": str(error)[:300]})
        os._exit(3)
    child.send({"t": "confined", "ok": True, **applied.as_dict(), "weak": bool(setup.get("weak", False))})
    serving = asyncio.create_task(child.serve())
    ctx = RecordingContext(str(setup["key"]), child, dict(setup.get("settings") or {}))
    module_name, _, function = str(setup["entry_point"]).partition(":")
    sys.path.insert(0, str(package))
    try:
        register = getattr(importlib.import_module(module_name), function)
        result = register(ctx)
        if inspect.isawaitable(result):
            await result
        calls = [
            {"m": method, "a": child.codec.encode(list(args)), "k": child.codec.encode(kwargs)}
            for method, args, kwargs in ctx.calls
        ]
    except Exception as error:
        child.send({"t": "failed", "error": {"type": type(error).__name__, "message": str(error)[:300]}})
        logging.getLogger("plugin").error("register failed: %s", traceback.format_exc()[-3000:])
        os._exit(5)
    child.send({"t": "registered", "calls": calls})
    child.send({"t": "ready"})
    await serving


def main() -> None:
    proto_in, proto_out = _protocol_streams()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_main(proto_in, proto_out))


if __name__ == "__main__":
    main()
