"""Compatibility (T011; R9): the running portal version against ``requires_portal`` and each required
capability's declared version against its range (001 registry). An incompatible plugin cannot be enabled
or updated; the reasons are named."""

from dataclasses import dataclass

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

import portalab
from portalab.capabilities.registry import CapabilityError, CapabilityRegistry
from portalab.modules.plugins.manifest.schema import Manifest


@dataclass(frozen=True, slots=True)
class Incompatibility:
    what: str
    detail: str


def _version(value: str) -> Version | None:
    try:
        return Version(value)
    except InvalidVersion:
        return None


def check(
    manifest: Manifest, capabilities: CapabilityRegistry, portal_version: str | None = None
) -> list[Incompatibility]:
    out: list[Incompatibility] = []
    portal = _version(portal_version or portalab.__version__)
    wanted = manifest.raw.get("requires_portal")
    if wanted and (portal is None or portal not in SpecifierSet(wanted, prereleases=True)):
        out.append(
            Incompatibility(
                "portal", f"needs portal {wanted}, running {portal_version or portalab.__version__}"
            )
        )
    for requirement in manifest.requires_capabilities:
        name = requirement["name"]
        try:
            spec = capabilities.spec(name)
        except CapabilityError:
            out.append(Incompatibility(name, "capability not available"))
            continue
        wanted_range = requirement.get("range")
        version = _version(spec.version)
        if wanted_range and (version is None or version not in SpecifierSet(wanted_range, prereleases=True)):
            out.append(Incompatibility(name, f"needs {name} {wanted_range}, found {spec.version}"))
    return out
