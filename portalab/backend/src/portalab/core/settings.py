"""Bootstrap settings — the ONLY configuration read from the environment (contracts/bootstrap-settings.md).

Everything else is declared to the Administration configuration system (spec 020, CD-011). Secrets come
from ``*_FILE`` paths; values are validated at start-up and errors never echo secret values.
"""

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


@dataclass(frozen=True, slots=True)
class BootstrapSettings:
    database_url: SecretValue
    secret_key: bytes = field(repr=False)
    bind_host: str = "0.0.0.0"  # noqa: S104 — container default, documented
    bind_port: int = 8080
    log_level: str = "INFO"
    data_dir: Path = Path("/var/lib/portalab")  # filesystem blob storage root (core.blobstore)


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

    return BootstrapSettings(
        database_url=database_url,
        secret_key=secret_key,
        bind_host=bind_host,
        bind_port=bind_port,
        log_level=log_level,
        data_dir=data_dir,
    )
