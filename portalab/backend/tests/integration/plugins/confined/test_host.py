"""030 T011 — the host of a confined plugin: start, registration replayed as proxies, calls, asks answered by
Portalab, callbacks, timeouts, crashes and restarts, refused confinement (Linux with Landlock ABI ≥ 4)."""

import asyncio
import textwrap
from pathlib import Path
from typing import Any

import pytest

from portalab.core.confinement import probe
from portalab.modules.plugins.confined.host import (
    ChildFailed,
    ChildHandler,
    ChildObject,
    ConfinedHost,
    Denied,
    Exposed,
    HostConfig,
)

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")

PLUGIN = textwrap.dedent(
    """
    import asyncio, socket
    from portalab.sdk import Principal

    class Provider:
        kind = "demo"
        label_key = "plugin.demo:kind"
        def facets(self):
            return ["a", "b"]
        async def search(self, query, principal):
            return {"query": query, "user": str(principal.user_id)}

    def register(ctx):
        ctx.permission("view", "See the demo")
        async def hello(principal, query, body):
            rows = await ctx.db.execute("SELECT 1 AS n", {})
            return {"hi": principal.user_id, "session": principal.session_id, "rows": rows, "q": dict(query)}
        async def slow(principal, query, body):
            await asyncio.sleep(30)
        async def stuck(principal, query, body):
            while True:
                pass
        async def crash(principal, query, body):
            import os
            os._exit(9)
        async def net(principal, query, body):
            socket.create_connection(("127.0.0.1", 5432), timeout=1)
        async def denied(principal, query, body):
            await ctx.http.get("https://example.org")
        async def consumer(envelope, context):
            return await context.idempotent_effect("k1")
        ctx.route("GET", "hello", hello, permission="plugin:demo.view", exposure="read")
        ctx.route("GET", "slow", slow, permission="plugin:demo.view")
        ctx.route("GET", "stuck", stuck, permission="plugin:demo.view")
        ctx.route("GET", "crash", crash, permission="plugin:demo.view")
        ctx.route("GET", "net", net, permission="plugin:demo.view")
        ctx.route("GET", "denied", denied, permission="plugin:demo.view")
        ctx.consume("on_user", ["user.verified"], consumer)
        ctx.search_provider(Provider())
    """
)


def _plugin(tmp_path: Path) -> Path:
    package = tmp_path / "pkg"
    (package / "demo_plugin").mkdir(parents=True)
    (package / "demo_plugin" / "__init__.py").write_text(PLUGIN)
    return package


class Recorder:
    def __init__(self) -> None:
        self.attempts: list[str] = []
        self.asks: list[str] = []

    async def ask(self, cap: str, args: Any, acting: Any = None) -> Any:
        self.asks.append(cap)
        if cap == "db.execute":
            return {"rows": [{"n": 1}], "rowcount": 1}
        raise Denied("denied", f"{cap} is not granted")

    async def attempt(self, kind: str, detail: Any) -> None:
        self.attempts.append(kind)


def _host(tmp_path: Path, recorder: Recorder, **overrides: Any) -> ConfinedHost:
    config = HostConfig(
        key="demo",
        version="1.0.0",
        package=_plugin(tmp_path),
        entry_point="demo_plugin:register",
        scratch=tmp_path / "scratch",
        deadline_s=overrides.pop("deadline_s", 2.0),
        forbidden=(tmp_path / "secret",),
        **overrides,
    )
    return ConfinedHost(config, recorder.ask, recorder.attempt)


def _route(calls: list[tuple[str, list[Any], dict[str, Any]]], path: str) -> ChildHandler:
    for method, args, _kwargs in calls:
        if method == "route" and args[1] == path:
            return args[2]
    raise AssertionError(path)


async def test_registers_calls_asks_and_callbacks(tmp_path: Path) -> None:
    from uuid import uuid4

    from portalab.core.authz_port import Principal

    recorder = Recorder()
    host = _host(tmp_path, recorder)
    try:
        calls = await host.start()
        assert host.confinement["seccomp"] is True and host.confinement["landlock_abi"] >= 4
        names = [c[0] for c in calls]
        assert names.count("route") == 6 and "consume" in names and "permission" in names
        user = uuid4()
        answer = await _route(calls, "hello")(Principal(user_id=user, session_id=uuid4()), {"a": "1"}, None)
        assert answer == {
            "hi": user,
            "session": None,
            "rows": [{"n": 1}],
            "q": {"a": "1"},
        }  # no session crosses
        provider = next(c[1][0] for c in calls if c[0] == "search_provider")
        assert (
            isinstance(provider, ChildObject) and provider.kind == "demo" and provider.facets() == ["a", "b"]
        )
        assert (await provider.search("x", Principal(user_id=user)))["query"] == "x"

        class Ctx:
            replay = False

            async def idempotent_effect(self, key: str) -> bool:
                return key == "k1"

            async def secret(self) -> str:
                return "no"

        consumer = next(c[1][2] for c in calls if c[0] == "consume")
        assert await consumer(None, Exposed(Ctx(), methods=("idempotent_effect",), attrs=("replay",))) is True
        with pytest.raises(ChildFailed):  # the plugin's own error: a socket refused by the kernel
            await _route(calls, "net")(Principal(user_id=user), {}, None)
        with pytest.raises(ChildFailed):  # Portalab refused the request
            await _route(calls, "denied")(Principal(user_id=user), {}, None)
        assert "http.request" in recorder.asks
    finally:
        await host.stop()


async def test_timeouts_and_crashes_are_attempts_and_the_process_comes_back(tmp_path: Path) -> None:
    from portalab.core.authz_port import Principal

    recorder = Recorder()
    host = _host(tmp_path, recorder, deadline_s=1.0)
    try:
        calls = await host.start()
        with pytest.raises(ChildFailed) as slow:
            await _route(calls, "slow")(Principal(), {}, None)
        assert slow.value.kind == "timeout"
        with pytest.raises(ChildFailed):
            await _route(calls, "stuck")(Principal(), {}, None)
        await asyncio.sleep(4)  # unresponsive → killed and restarted (backoff 1 s)
        assert "unresponsive" in recorder.attempts
        first = host.process.pid if host.process else None
        with pytest.raises(ChildFailed):
            await _route(calls, "crash")(Principal(), {}, None)
        for _ in range(40):
            await asyncio.sleep(0.25)
            if host.state == "running" and host.process and host.process.pid != first:
                break
        assert "crash" in recorder.attempts and host.state == "running"
        assert (await _route(host.calls, "hello")(Principal(), {}, None))["rows"] == [{"n": 1}]
    finally:
        await host.stop()


async def test_a_process_that_would_read_a_secret_never_starts(tmp_path: Path) -> None:
    import portalab

    recorder = Recorder()
    host = _host(tmp_path, recorder)
    host.config.forbidden = (Path(portalab.__file__).parent / "core",)
    with pytest.raises(RuntimeError):
        await host.start()
