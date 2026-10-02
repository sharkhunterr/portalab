"""Spec 021 fixtures: authz + privacy + identity wired together as in production (fast Argon2 for tests)."""

from dataclasses import dataclass
from pathlib import Path

from portalab.core.time import Clock
from portalab.modules.administration.module import AdministrationModule
from portalab.modules.identity.services import (
    visibility as _identity_visibility,  # noqa: F401 — profile_field
)
from portalab.modules.privacy.module import PrivacyModule
from tests.authz_fixtures import AuthzPlatform, make_administration, make_platform


@dataclass
class FullPlatform(AuthzPlatform):
    privacy: PrivacyModule
    administration: AdministrationModule


def make_full_platform(database: object, blob_root: Path, clock: Clock | None = None) -> FullPlatform:
    base = make_platform(database, blob_root, clock)  # type: ignore[arg-type]
    privacy = PrivacyModule(
        base.database, base.authz.engine.events, base.authz.audit, base.identity.capabilities, clock=clock
    )
    privacy.register_capabilities()
    base.identity.visibility = privacy.filter  # identity's module is wired by create_app(identity=...)
    return FullPlatform(base.authz, base.identity, privacy, make_administration(base))
