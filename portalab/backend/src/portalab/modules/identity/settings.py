"""Identity settings — declared to the Administration configuration system (plan §7, CD-011).

Values are code defaults until the Configuration step resolves the hierarchy; services receive an
:class:`IdentityConfig` snapshot, so the source of the values can change without touching them.
Durations are admin policy (CANONICAL_DECISIONS OQ-7 default); they are not product rules.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:identity"

RegistrationMode = Literal["open", "invite_only"]
"""``open``: self-registration + verification. ``invite_only``: self-registration closed; accounts are created
by the Admin (``POST /users``) and activated by their verification token (decision 2026-10-01, CD-036)."""


class PasswordPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_length: int = Field(default=12, ge=8, le=128)
    max_length: int = Field(default=256, ge=16, le=1024)


class Argon2Params(BaseModel):
    """Argon2id cost parameters (OWASP baseline); changing them triggers rehash-on-login."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_cost: int = Field(default=3, ge=1, le=20)
    memory_cost_kib: int = Field(default=65536, ge=8192, le=1048576)
    parallelism: int = Field(default=4, ge=1, le=16)


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    session_idle_minutes: int = 7 * 24 * 60
    session_absolute_hours: int = 30 * 24
    verification_ttl_hours: int = 72
    deletion_grace_days: int = 30
    dormancy_days: int = 180
    export_ttl_hours: int = 7 * 24
    registration_mode: RegistrationMode = "invite_only"
    password_policy: PasswordPolicy = field(default_factory=PasswordPolicy)
    argon2_params: Argon2Params = field(default_factory=Argon2Params)


_DEFAULTS = IdentityConfig()

_DECLARATIONS: tuple[tuple[str, Any, Any, str], ...] = (
    (
        "identity.sessionIdleMinutes",
        int,
        _DEFAULTS.session_idle_minutes,
        "Minutes of inactivity after which a session expires.",
    ),
    (
        "identity.sessionAbsoluteHours",
        int,
        _DEFAULTS.session_absolute_hours,
        "Maximum session lifetime in hours, regardless of activity.",
    ),
    (
        "identity.verificationTtlHours",
        int,
        _DEFAULTS.verification_ttl_hours,
        "Validity of an account verification token, in hours.",
    ),
    (
        "identity.deletionGraceDays",
        int,
        _DEFAULTS.deletion_grace_days,
        "Days an account stays in Pending Deletion (cancellable) before final deletion.",
    ),
    (
        "identity.dormancyDays",
        int,
        _DEFAULTS.dormancy_days,
        "Days without sign-in after which an Active account is marked Inactive.",
    ),
    (
        "identity.exportTtlHours",
        int,
        _DEFAULTS.export_ttl_hours,
        "Hours a personal-data export stays downloadable before it is deleted.",
    ),
    (
        "identity.registrationMode",
        RegistrationMode,
        _DEFAULTS.registration_mode,
        "open: self-registration; invite_only: accounts are created by the Admin.",
    ),
    (
        "identity.passwordPolicy",
        PasswordPolicy,
        _DEFAULTS.password_policy,
        "Password length policy for local credentials.",
    ),
    (
        "identity.argon2Params",
        Argon2Params,
        _DEFAULTS.argon2_params,
        "Argon2id parameters; a change re-hashes passwords on the next sign-in.",
    ),
)


def declare_identity_settings(catalog: SettingCatalog = default_catalog) -> None:
    """Declare the identity keys through the kernel ``declare_setting`` (idempotent per catalog)."""
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, description in _DECLARATIONS:
        if key in known:
            continue
        declare(
            scope="module",
            key=key,
            schema=schema,
            default=default,
            owner=OWNER,
            description=description,
        )


declare_identity_settings()
