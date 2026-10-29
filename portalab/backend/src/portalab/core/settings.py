"""Bootstrap settings — the ONLY configuration read from the environment (contracts/bootstrap-settings.md).

Everything else is declared to the Administration configuration system (spec 020, CD-011). Secrets come
from ``*_FILE`` paths; values are validated at start-up and errors never echo secret values.
"""

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from portalab.core.logging import register_secret_value
from portalab.core.secrets import SecretValue

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
MIN_SECRET_KEY_BYTES = 32


class SettingsError(ValueError):
    """Invalid or missing bootstrap setting (message never contains secret values)."""


# 028: the machine itself and the local networks; the proxy on the machine itself
HEALTH_NETWORKS = ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
TRUSTED_PROXIES = ("127.0.0.1",)
SETUP_NETWORKS = (
    HEALTH_NETWORKS  # #275: where a portal not yet set up may be set up from (never the internet)
)


@dataclass(frozen=True, slots=True)
class BootstrapSettings:
    database_url: SecretValue
    secret_key: bytes = field(repr=False)
    bind_host: str = "0.0.0.0"  # noqa: S104 — container default, documented
    bind_port: int = 8080
    log_level: str = "INFO"
    data_dir: Path = Path("/var/lib/portalab")  # filesystem blob storage root (core.blobstore)
    # 028: who may ask the health checks, and the reverse proxies whose X-Forwarded-For is believed
    health_networks: tuple[str, ...] = HEALTH_NETWORKS
    trusted_proxies: tuple[str, ...] = TRUSTED_PROXIES
    setup_networks: tuple[str, ...] = SETUP_NETWORKS


def normalize_database_url(url: str) -> str:
    """Accept ``postgres://`` / ``postgresql://`` and force the asyncpg driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise SettingsError(
        "DATABASE_URL must be a PostgreSQL URL (postgresql://…); other databases are unsupported"
    )


def _read_file(name: str, path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SettingsError(f"{name} points to an unreadable file") from exc


def _networks(env: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = env.get(name)
    if raw is None:
        return default
    values = tuple(v.strip() for v in raw.split(",") if v.strip())
    for value in values:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise SettingsError(f"{name} must be a comma-separated list of addresses or networks") from exc
    return values


def load_settings(env: Mapping[str, str] | None = None) -> BootstrapSettings:
    """Load and validate bootstrap settings; fail fast with a clear, secret-free message."""
    env = os.environ if env is None else env

    inline_url, url_file = env.get("DATABASE_URL"), env.get("DATABASE_URL_FILE")
    if inline_url and url_file:
        raise SettingsError("set either DATABASE_URL or DATABASE_URL_FILE, not both")
    if url_file:
        raw_url = _read_file("DATABASE_URL_FILE", url_file)
    elif inline_url:
        raw_url = inline_url
    else:
        raise SettingsError("DATABASE_URL_FILE (or DATABASE_URL) is required")
    database_url = SecretValue(normalize_database_url(raw_url))

    key_file = env.get("SECRET_KEY_FILE")
    if not key_file:
        raise SettingsError("SECRET_KEY_FILE is required (inline secret keys are not accepted)")
    key_text = _read_file("SECRET_KEY_FILE", key_file)
    secret_key = key_text.encode("utf-8")
    if len(secret_key) < MIN_SECRET_KEY_BYTES:
        raise SettingsError(f"SECRET_KEY_FILE must contain at least {MIN_SECRET_KEY_BYTES} bytes")
    register_secret_value(key_text)

    bind_host = env.get("BIND_HOST", "0.0.0.0")  # noqa: S104
    try:
        bind_port = int(env.get("BIND_PORT", "8080"))
    except ValueError as exc:
        raise SettingsError("BIND_PORT must be an integer") from exc
    if not 1 <= bind_port <= 65535:
        raise SettingsError("BIND_PORT must be between 1 and 65535")

    log_level = env.get("LOG_LEVEL", "INFO").upper()
    if log_level not in LOG_LEVELS:
        raise SettingsError(f"LOG_LEVEL must be one of {sorted(LOG_LEVELS)}")

    data_dir = Path(env.get("DATA_DIR", "/var/lib/portalab"))
    if not data_dir.is_absolute():
        raise SettingsError("DATA_DIR must be an absolute path")

    health_networks = _networks(env, "HEALTH_NETWORKS", HEALTH_NETWORKS)
    trusted_proxies = _networks(env, "TRUSTED_PROXIES", TRUSTED_PROXIES)
    setup_networks = _networks(env, "SETUP_NETWORKS", SETUP_NETWORKS)

    return BootstrapSettings(
        health_networks=health_networks,
        trusted_proxies=trusted_proxies,
        setup_networks=setup_networks,
        database_url=database_url,
        secret_key=secret_key,
        bind_host=bind_host,
        bind_port=bind_port,
        log_level=log_level,
        data_dir=data_dir,
    )
