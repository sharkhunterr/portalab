"""ConfinedHost (spec 030, R1-R4): Portalab's side of one confined plugin process.

It starts the process with an empty environment and nothing but three pipes, refuses a process that did not
confine itself as required, replays nothing itself (the caller does, from :attr:`calls`), calls the plugin's
handlers within a deadline and a concurrency limit, answers the plugin's requests through ``on_ask`` (where
the grants are checked), restarts a process that died, and reports every attempt (timeout, crash, oversize,
busy, refused confinement) through ``on_attempt`` — 023's guard counts them toward quarantine.
"""

import asyncio
import contextlib
import hashlib
import itertools
import json
import logging
import os
import signal
import sys
import sysconfig
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from portalab.core.confinement import MIN_LANDLOCK_ABI
from portalab.sdk.confined.protocol import MAX_LINE, Codec, Oversize, ProtocolError, decode_line, encode_line

log = logging.getLogger("portalab.plugins.confined")

AskHandler = Callable[[str, Mapping[str, Any], Any], Awaitable[Any]]  # (cap, args, acting principal)
AttemptHandler = Callable[[str, Mapping[str, Any]], Awaitable[None]]


class ChildFailed(RuntimeError):
    """The plugin's process failed a call (its error, a timeout, its death); members get a clean failure."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class Busy(ChildFailed):
    pass


class Denied(Exception):
    """Raised by an ``on_ask`` handler: the request is refused (and counted as an attempt by the caller)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Exposed:
    """A Portalab object handed to a plugin call with only these async methods and attributes."""

    target: Any
    methods: tuple[str, ...] = ()
    attrs: tuple[str, ...] = ()
    __portalab_reference__ = True


@dataclass
class HostConfig:
    key: str
    version: str
    package: Path
    entry_point: str
    scratch: Path
    settings: Mapping[str, Any] = field(default_factory=dict)
    memory_mb: int = 384
    weak: bool = False
    deadline_s: float = 5.0
    concurrency: int = 8
    forbidden: tuple[Path, ...] = ()  # data folder, secret files: must not be readable by the process
    python: str = sys.executable


def child_read_paths(forbidden: Iterable[Path] = ()) -> list[Path]:
    """What a plugin process may read: Python, its libraries and Portalab's code — never a folder holding
    the portal's data or secrets (refused, so the process does not start)."""
    import portalab

    paths: set[Path] = set()
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        value = sysconfig.get_paths().get(key)
        if value:
            paths.add(Path(value))
    paths.add(Path(portalab.__file__).resolve().parent.parent)
    paths.add(Path(sys.executable).resolve().parent)
    paths.add(Path(sys.base_prefix) / "lib")
    for system in ("/usr/lib", "/lib", "/lib64", "/usr/lib64", "/usr/local/lib"):
        if Path(system).exists():
            paths.add(Path(system))
    resolved = sorted({p.resolve() for p in paths if p.exists()})
    for secret in forbidden:
        secret = secret.resolve()
        for path in resolved:
            if secret == path or path in secret.parents:
                raise RuntimeError(f"a plugin process would read {secret}")
    return resolved


def _is_member(value: Any) -> bool:
    from portalab.core.authz_port import Principal

    return isinstance(value, Principal) and value.user_id is not None


def _close(process: asyncio.subprocess.Process) -> None:
    """Close the pipes' transport of a process that ended (nothing left for the event loop to finish)."""
    transport = getattr(process, "_transport", None)
    with contextlib.suppress(Exception):
        if transport is not None:
            transport.close()


class ChildHandler:
    """A plugin callable, called in its process."""

    def __init__(self, host: "ConfinedHost", hid: int) -> None:
        self.host = host
        self.hid = hid

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self.host.call(self.hid, None, args, kwargs)


class ChildObject:
    """A plugin object (a provider): its async methods call the process; sync methods without arguments
    answer what they returned at registration; simple attributes are copied."""

    def __init__(self, host: "ConfinedHost", ref: Mapping[str, Any]) -> None:
        self._host = host
        self._hid = int(ref["$o"])
        for name, value in dict(host.codec.decode(ref.get("attrs") or {})).items():
            if not name.startswith("_"):
                object.__setattr__(self, name, value)
        for name in ref.get("methods") or []:
            object.__setattr__(self, str(name), self._method(str(name)))
        for name, value in dict(ref.get("values") or {}).items():
            decoded = host.codec.decode(value)
            object.__setattr__(self, str(name), lambda decoded=decoded: decoded)

    def _method(self, name: str) -> Callable[..., Awaitable[Any]]:
        async def call(*args: Any, **kwargs: Any) -> Any:
            return await self._host.call(self._hid, name, args, kwargs)

        return call


class ConfinedHost:
    def __init__(self, config: HostConfig, on_ask: AskHandler, on_attempt: AttemptHandler) -> None:
        self.config = config
        self.on_ask = on_ask
        self.on_attempt = on_attempt
        self.codec = Codec(refer=self._refer, resolve=self._resolve)
        self.process: asyncio.subprocess.Process | None = None
        self.calls: list[tuple[str, list[Any], dict[str, Any]]] = []
        self.signature: str | None = None
        self.confinement: dict[str, Any] = {}
        self.state = "stopped"
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._exposed: dict[int, Exposed] = {}
        self._acting: dict[int, Any] = {}  # call id → the member it is for (a Principal among its arguments)
        self._slots = asyncio.Semaphore(config.concurrency)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._ready: asyncio.Event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._failures = 0
        self._last_pong = 0.0
        self._pings = itertools.count(1)
        self._log_budget = (0.0, 0)

    # --- references from the process -------------------------------------------------------------------
    def _resolve(self, ref: dict[str, Any]) -> Any:
        if "$h" in ref:
            return ChildHandler(self, int(ref["$h"]))
        return ChildObject(self, ref)

    def _refer(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, Exposed):
            return {"$unsupported": type(value).__name__}
        oid = next(self._ids)
        self._exposed[oid] = value
        attrs = {name: getattr(value.target, name, None) for name in value.attrs}
        return {
            "$o": oid,
            "side": "parent",
            "methods": list(value.methods),
            "attrs": self.codec.encode(attrs),
        }

    # --- lifecycle -------------------------------------------------------------------------------------
    async def start(self) -> list[tuple[str, list[Any], dict[str, Any]]]:
        async with self._lock:
            if self.state == "running" and self.process is not None and self.process.returncode is None:
                return self.calls
            return await self._spawn()

    async def _spawn(self) -> list[tuple[str, list[Any], dict[str, Any]]]:
        cfg = self.config
        cfg.scratch.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            cfg.scratch.chmod(0o700)
        env = {
            "LANG": "C.UTF-8",
            "PYTHONHASHSEED": "random",
            "PYTHONDONTWRITEBYTECODE": "1",
            "MALLOC_ARENA_MAX": "2",
            "HOME": str(cfg.scratch),
            "TMPDIR": str(cfg.scratch),
        }
        setup = {
            "key": cfg.key,
            "version": cfg.version,
            "package": str(cfg.package.resolve()),
            "entry_point": cfg.entry_point,
            "scratch": str(cfg.scratch.resolve()),
            "read": [str(p) for p in child_read_paths(cfg.forbidden)],
            "memory_mb": cfg.memory_mb,
            "weak": cfg.weak,
            "settings": self.codec.encode(dict(cfg.settings)),
        }
        self.state = "starting"
        self._ready = asyncio.Event()
        self.process = await asyncio.create_subprocess_exec(
            cfg.python,
            "-I",
            "-m",
            "portalab.sdk.confined.child",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cfg.scratch),
            close_fds=True,
            start_new_session=True,
            limit=MAX_LINE + 1,
        )
        process = self.process
        self._write({"t": "hello", "setup": setup})
        self._spawn_task(self._read_stderr(process))
        registered: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._spawn_task(self._read_stdout(process, registered))
        try:
            message = await asyncio.wait_for(registered, timeout=60)  # a loaded host starts slower
        except TimeoutError:
            await self._kill(process)
            self.state = "failed"
            await self.on_attempt("timeout", {"phase": "start"})
            raise ChildFailed("timeout", "the plugin did not start in time") from None
        if message["t"] != "registered":
            await self._kill(process)
            self.state = "failed"
            raise ChildFailed(message.get("kind", "failed"), str(message.get("error", "failed"))[:300])
        self.calls = [
            (
                str(c["m"]),
                list(self.codec.decode(c.get("a") or [])),
                dict(self.codec.decode(c.get("k") or {})),
            )
            for c in message.get("calls", [])
        ]
        self.signature = hashlib.sha256(
            json.dumps(message.get("calls", []), sort_keys=True).encode()
        ).hexdigest()
        await asyncio.wait_for(self._ready.wait(), timeout=30)
        self.state = "running"
        self._last_pong = time.monotonic()
        self._spawn_task(self._heartbeat(process))
        return self.calls

    async def stop(self) -> None:
        process, self.process = self.process, None
        self.state = "stopped"
        if process is None or process.returncode is not None:
            return
        with contextlib.suppress(Exception):
            self._write({"t": "stop"}, process)
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            await self._kill(process)
        _close(process)
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _kill(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5)
        _close(process)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ChildFailed("crash", "the plugin's process stopped"))
        self._pending.clear()

    def _spawn_task(self, coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # --- calls -----------------------------------------------------------------------------------------
    async def call(self, hid: int, method: str | None, args: Iterable[Any], kwargs: Mapping[str, Any]) -> Any:
        if self.state != "running":
            await self.start()
        # at most ``concurrency`` calls at once: the next ones wait for a place, within their deadline
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self.config.deadline_s)
        except TimeoutError:
            await self.on_attempt("busy", {"concurrency": self.config.concurrency})
            raise Busy("busy", "the plugin is busy") from None
        try:
            return await self._call(hid, method, args, kwargs)
        finally:
            self._slots.release()

    async def _call(
        self, hid: int, method: str | None, args: Iterable[Any], kwargs: Mapping[str, Any]
    ) -> Any:
        cid = next(self._ids)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[cid] = future
        exposed_before = set(self._exposed)
        acting = next((a for a in args if _is_member(a)), None)
        if acting is not None:
            self._acting[cid] = acting
        message = {
            "t": "call",
            "id": cid,
            "hid": hid,
            "method": method,
            "deadline_ms": int(self.config.deadline_s * 1000),
            "args": self.codec.encode(list(args)),
            "kwargs": self.codec.encode(dict(kwargs)),
        }
        try:
            self._write(message)
            answer = await asyncio.wait_for(future, timeout=self.config.deadline_s)
        except TimeoutError:
            self._pending.pop(cid, None)
            await self.on_attempt("timeout", {"deadline_s": self.config.deadline_s})
            self._spawn_task(self._check_alive())
            raise ChildFailed("timeout", "the plugin did not answer in time") from None
        except Oversize:
            self._pending.pop(cid, None)
            raise ChildFailed("oversize", "the request is too large") from None
        finally:
            self._acting.pop(cid, None)
            for oid in set(self._exposed) - exposed_before:
                self._exposed.pop(oid, None)
        if not answer.get("ok"):
            error = answer.get("error") or {}
            raise ChildFailed("error", f"{error.get('type', 'Error')}: {str(error.get('message', ''))[:300]}")
        return self.codec.decode(answer.get("value"))

    async def _check_alive(self) -> None:
        """After a timeout: a process that no longer answers is restarted (its event loop is stuck)."""
        process = self.process
        if process is None:
            return
        asked = time.monotonic()
        with contextlib.suppress(Exception):
            self._write({"t": "ping", "n": next(self._pings)}, process)
        await asyncio.sleep(2)
        if self._last_pong < asked and self.process is process:
            await self.on_attempt("unresponsive", {})
            await self._restart(process)

    async def _restart(self, process: asyncio.subprocess.Process) -> None:
        await self._kill(process)
        if self.process is not process:
            return
        self.process = None
        self.state = "failed"
        self._failures += 1
        await asyncio.sleep(min(30.0, (1.0, 5.0, 30.0)[min(self._failures, 3) - 1]))
        if self.state == "failed":
            with contextlib.suppress(Exception):
                previous = self.signature
                await self.start()
                if previous is not None and self.signature != previous:
                    log.warning("plugin %s registered differently after a restart", self.config.key)

    async def _heartbeat(self, process: asyncio.subprocess.Process) -> None:
        while self.process is process and process.returncode is None:
            await asyncio.sleep(10)
            if time.monotonic() - self._last_pong > 35:
                await self.on_attempt("unresponsive", {})
                await self._restart(process)
                return
            with contextlib.suppress(Exception):
                self._write({"t": "ping", "n": next(self._pings)}, process)

    # --- wire ------------------------------------------------------------------------------------------
    def _write(self, message: Mapping[str, Any], process: asyncio.subprocess.Process | None = None) -> None:
        target = process or self.process
        if target is None or target.stdin is None:
            raise ChildFailed("crash", "the plugin's process is not running")
        target.stdin.write(encode_line(message))

    async def _read_stdout(
        self, process: asyncio.subprocess.Process, registered: asyncio.Future[dict[str, Any]]
    ) -> None:
        assert process.stdout is not None
        confined = False
        while True:
            try:
                raw = await process.stdout.readline()
            except (ValueError, asyncio.LimitOverrunError):
                await self.on_attempt("oversize", {})
                await self._restart(process)
                return
            if not raw:
                break
            try:
                message = decode_line(raw)
            except ProtocolError:
                await self.on_attempt("oversize", {"malformed": True})
                continue
            kind = message["t"]
            if kind == "confined":
                confined = self._accept_confinement(message)
                if not confined:
                    if not registered.done():
                        registered.set_result(
                            {"t": "refused", "kind": "confinement", "error": "not confined"}
                        )
                    await self.on_attempt(
                        "confinement", {k: message.get(k) for k in ("landlock_abi", "seccomp")}
                    )
                    await self._kill(process)
                    return
            elif not confined:
                await self.on_attempt("confinement", {"before": kind})
                await self._kill(process)
                return
            elif kind == "registered" and not registered.done():
                registered.set_result(message)
            elif kind == "failed" and not registered.done():
                registered.set_result({"t": "failed", "kind": "error", "error": message.get("error")})
            elif kind == "ready":
                self._ready.set()
            elif kind == "result":
                future = self._pending.pop(int(message.get("id", 0)), None)
                if future is not None and not future.done():
                    future.set_result(message)
            elif kind == "ask":
                self._spawn_task(self._answer(message, process))
            elif kind == "pong":
                self._last_pong = time.monotonic()
        code = await process.wait()
        if not registered.done():
            registered.set_result({"t": "failed", "kind": "crash", "error": f"exited with {code}"})
            return
        if self.process is process and self.state == "running":
            await self.on_attempt("memory" if code in (-9, 137) else "crash", {"exit": code})
            await self._restart(process)

    def _accept_confinement(self, message: Mapping[str, Any]) -> bool:
        if not message.get("ok"):
            return False
        self.confinement = {
            k: message.get(k) for k in ("landlock_abi", "seccomp", "rlimits", "scoped", "weak")
        }
        if self.config.weak:
            return True
        return int(message.get("landlock_abi") or 0) >= MIN_LANDLOCK_ABI and bool(message.get("seccomp"))

    async def _answer(self, message: Mapping[str, Any], process: asyncio.subprocess.Process) -> None:
        aid = message.get("id")
        cap = str(message.get("cap", ""))
        try:
            args = self.codec.decode(message.get("args") or {})
            if cap == "callback":
                value = await self._callback(args)
            elif cap == "log":
                self._log_line(str(dict(args).get("message", "")))
                value = {}
            else:
                cid = message.get("cid")
                acting = self._acting.get(cid) if isinstance(cid, int) else None
                value = await self.on_ask(cap, dict(args), acting)
            reply = {"t": "answer", "id": aid, "ok": True, "value": self.codec.encode(value)}
        except Denied as error:
            reply = {
                "t": "answer",
                "id": aid,
                "ok": False,
                "error": {"code": error.code, "message": str(error)},
            }
        except Exception as error:  # a failure of Portalab's side: the plugin gets a clean refusal
            log.warning(
                "plugin %s ask %s failed: %s %s", self.config.key, cap, type(error).__name__, str(error)[:600]
            )
            reply = {"t": "answer", "id": aid, "ok": False, "error": {"code": "failed", "message": "failed"}}
        with contextlib.suppress(Exception):
            self._write(reply, process)

    async def _callback(self, args: Mapping[str, Any]) -> Any:
        exposed = self._exposed.get(int(args.get("oid", 0)))
        method = str(args.get("method", ""))
        if exposed is None or method not in exposed.methods:
            raise Denied("denied", "no such callback")
        result = getattr(exposed.target, method)(
            *list(args.get("args") or []), **dict(args.get("kwargs") or {})
        )
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def _read_stderr(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        while True:
            try:
                raw = await process.stderr.readline()
            except (ValueError, asyncio.LimitOverrunError):
                continue
            if not raw:
                return
            self._log_line(raw.decode("utf-8", errors="replace"))

    def _log_line(self, line: str) -> None:
        start, count = self._log_budget
        now = time.monotonic()
        if now - start > 10:
            start, count = now, 0
        count += 1
        self._log_budget = (start, count)
        if count <= 50:
            log.info("plugin %s: %s", self.config.key, line.rstrip()[:4096])
