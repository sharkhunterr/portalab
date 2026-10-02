"""Authorization settings declared to the Administration configuration system (plan §7, CD-011)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:authz"


@dataclass(frozen=True, slots=True)
class AuthzConfig:
    confirmation_ttl_seconds: int = 300
    audit_context_max_bytes: int = 4096


_DEFAULTS = AuthzConfig()
_DECLARATIONS = (
    (
        "authz.confirmationTtlSeconds",
        _DEFAULTS.confirmation_ttl_seconds,
        "Validity of a confirmation token for a sensitive action, in seconds.",
    ),
    (
        "authz.auditContextMaxBytes",
        _DEFAULTS.audit_context_max_bytes,
        "Maximum size of the (redacted) context stored with an audit entry.",
    ),
)


def declare_authz_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, default, description in _DECLARATIONS:
        if key not in known:
            declare(
                scope="module", key=key, schema=int, default=default, owner=OWNER, description=description
            )


declare_authz_settings()
