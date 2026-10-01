"""Bootstrap settings (contracts/bootstrap-settings.md): env/_FILE only, fail fast, no secret in errors."""

from pathlib import Path

import pytest

from portalab.core.settings import SettingsError, load_settings, normalize_database_url

pytestmark = pytest.mark.unit

URL = "postgresql://portalab:pw-123456@db:5432/portalab"


@pytest.fixture
def key_file(tmp_path: Path) -> str:
    path = tmp_path / "secret_key"
    path.write_text("x" * 48)
    return str(path)


def test_loads_from_files(tmp_path: Path, key_file: str) -> None:
    url_file = tmp_path / "db_url"
    url_file.write_text(URL + "\n")
    settings = load_settings(
        {
            "DATABASE_URL_FILE": str(url_file),
            "SECRET_KEY_FILE": key_file,
            "BIND_PORT": "9000",
            "LOG_LEVEL": "debug",
        }
    )
    assert settings.database_url.reveal() == "postgresql+asyncpg://portalab:pw-123456@db:5432/portalab"
    assert settings.bind_port == 9000
    assert settings.log_level == "DEBUG"
    assert "pw-123456" not in repr(settings)


def test_defaults(key_file: str) -> None:
    settings = load_settings({"DATABASE_URL": URL, "SECRET_KEY_FILE": key_file})
    assert (settings.bind_host, settings.bind_port, settings.log_level) == ("0.0.0.0", 8080, "INFO")


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({}, "DATABASE_URL_FILE"),
        ({"DATABASE_URL": URL}, "SECRET_KEY_FILE"),
        ({"DATABASE_URL": "mysql://u:p@h/db"}, "PostgreSQL"),
        ({"DATABASE_URL": URL, "BIND_PORT": "70000"}, "BIND_PORT"),
        ({"DATABASE_URL": URL, "BIND_PORT": "http"}, "BIND_PORT"),
        ({"DATABASE_URL": URL, "LOG_LEVEL": "LOUD"}, "LOG_LEVEL"),
        ({"DATABASE_URL": URL, "DATABASE_URL_FILE": "/x"}, "not both"),
    ],
)
def test_invalid_settings_fail_fast_without_leaking(env: dict[str, str], message: str, key_file: str) -> None:
    env = {"SECRET_KEY_FILE": key_file, **env} if "SECRET_KEY_FILE" not in message else env
    with pytest.raises(SettingsError, match=message) as excinfo:
        load_settings(env)
    assert "pw-123456" not in str(excinfo.value)


def test_short_or_missing_key_file(tmp_path: Path) -> None:
    short = tmp_path / "short"
    short.write_text("tiny")
    with pytest.raises(SettingsError, match="at least"):
        load_settings({"DATABASE_URL": URL, "SECRET_KEY_FILE": str(short)})
    with pytest.raises(SettingsError, match="unreadable"):
        load_settings({"DATABASE_URL": URL, "SECRET_KEY_FILE": str(tmp_path / "missing")})


def test_business_settings_are_never_read_from_env(key_file: str) -> None:
    settings = load_settings(
        {"DATABASE_URL": URL, "SECRET_KEY_FILE": key_file, "I18N_DEFAULT_LANGUAGE": "fr"}
    )
    assert not hasattr(settings, "i18n_default_language")


def test_normalize_url_variants() -> None:
    assert normalize_database_url("postgres://a/b") == "postgresql+asyncpg://a/b"
    assert normalize_database_url("postgresql+asyncpg://a/b") == "postgresql+asyncpg://a/b"
