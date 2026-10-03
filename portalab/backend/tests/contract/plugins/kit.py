"""Plugin-author contract kit (023 T035) — usable in a plugin's own CI against a test portal:

* ``check_manifest(path)`` — the manifest validates and the code passes the import scanner;
* ``check_contributions(module, key, points)`` — after enabling (and a restart), every listed extension
  point holds an active contribution and none is in conflict;
* ``check_removal(module, key)`` — after disable/quarantine every registry is empty for the plugin;
* ``check_guard(module, key, failing_route)`` — a failing hook is contained (``plugin.hook_failed``)."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from portalab.modules.plugins.scanner.scanner import scan_package
from portalab.modules.plugins.store.package import read_manifest


def check_manifest(path: Path) -> None:
    manifest = read_manifest(path)
    if manifest.entry_point:
        findings = scan_package(path, manifest.entry_point.split(":")[0].split(".")[0])
        assert findings == [], findings


async def check_contributions(module: Any, key: str, points: Iterable[str]) -> None:
    entries = [e for e in await module.ledger.entries(key) if e.state != "removed"]
    active = {e.point for e in entries if e.state == "active"}
    conflicts = [(e.point, e.contribution_id, e.detail) for e in entries if e.state == "conflict"]
    assert conflicts == [], conflicts
    missing = sorted(set(points) - active)
    assert missing == [], missing


async def check_removal(module: Any, key: str) -> None:
    leftovers = await module.registries.leftovers(f"plugin:{key}")
    assert leftovers == {}, leftovers


async def check_guard(module: Any, key: str, failing_route: str) -> None:
    from portalab.core.authz_port import Principal
    from portalab.modules.plugins.guard.guard import PluginHookFailed

    route = module.registries.routes.get(key, "GET", failing_route)
    assert route is not None
    try:
        await route.handler(Principal(channel="system"), {}, None)
    except PluginHookFailed:
        return
    raise AssertionError("a failing hook must be contained")
