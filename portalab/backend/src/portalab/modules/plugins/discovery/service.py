"""Discovery (T029; R15): what could be installed — packages dropped into ``plugins/available/`` (never
fetched from the internet automatically) — each with its maturity, deprecation notice and a compatibility
and dependency preview, next to what is installed. Marketplace plugin products reference packages the
Admin installed (015 R10)."""

from typing import Any

from portalab.modules.plugins.compat.checker import check
from portalab.modules.plugins.lifecycle.service import Lifecycle
from portalab.modules.plugins.resolver.resolver import problems_for
from portalab.modules.plugins.store.package import read_manifest


class Discovery:
    def __init__(self, lifecycle: Lifecycle) -> None:
        self.lifecycle = lifecycle

    async def available(self) -> list[dict[str, Any]]:
        installed = {p.key: p for p in await self.lifecycle.all()}
        manifests = await self.lifecycle.manifests()
        out: list[dict[str, Any]] = []
        for path in self.lifecycle.store.packages_available():
            try:
                manifest = read_manifest(path)
            except Exception as error:
                out.append({"package": path.name, "valid": False, "problem": type(error).__name__})
                continue
            preview = {**manifests, manifest.key: manifest}
            plugin = installed.get(manifest.key)
            out.append(
                {
                    "package": path.name,
                    "valid": True,
                    "key": manifest.key,
                    "name": manifest.name,
                    "version": manifest.version,
                    "maturity": manifest.maturity,
                    "deprecation_notice": manifest.raw.get("deprecation_notice"),
                    "scope": manifest.scope,
                    "code": manifest.entry_point is not None,
                    "installed_version": plugin.current_version if plugin else None,
                    "state": plugin.state if plugin else None,
                    "compatibility": [
                        f"{i.what}: {i.detail}" for i in check(manifest, self.lifecycle.capabilities)
                    ],
                    "dependencies": [p.detail for p in problems_for(manifest.key, preview)],
                }
            )
        return out
