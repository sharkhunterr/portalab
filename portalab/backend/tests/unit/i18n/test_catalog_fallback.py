"""026 T015/T037/T044 — missing key ⇒ fallback value + stat, never raises; base ⊕ override; no
cross-namespace leakage; ETag = content hash; plugin catalogs namespaced, isolated and withdrawn."""

import json
from pathlib import Path

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.catalog.plugins import PluginCatalogError, PluginCatalogs
from portalab.modules.i18n.catalog.service import CatalogService


@pytest.fixture
def service(tmp_path: Path) -> CatalogService:
    for lang, messages in {
        "en": {"hello": "Hello {name}", "only_en": "English only"},
        "fr": {"hello": "Bonjour {name}"},
    }.items():
        (tmp_path / lang).mkdir()
        (tmp_path / lang / "core.json").write_text(json.dumps(messages), encoding="utf-8")
        (tmp_path / lang / "other.json").write_text(json.dumps({"secret_ns": "x"}), encoding="utf-8")
    return CatalogService(None, locales_dir=tmp_path, plugins=PluginCatalogs())  # type: ignore[arg-type]


FR = LocaleContext(language="fr", locale="fr", fallback_chain=("en",))


def test_fallback_and_stats(service: CatalogService) -> None:
    assert service.t("hello", FR, {"name": "Léa"}) == "Bonjour Léa"
    assert service.t("only_en", FR) == "English only"  # falls back
    assert service.t("nope", FR) == "nope"  # never empty, never raises
    assert service._missing[("core", "fr", "only_en")] == 1 and service._missing[("core", "fr", "nope")] == 1
    assert service.t("secret_ns", FR) == "secret_ns"  # other namespace does not leak


def test_overrides_and_etag(service: CatalogService) -> None:
    first, version = service.bundle("core", FR)
    assert first["hello"] == "Bonjour {name}" and first["only_en"] == "English only"
    service._overrides = {("core", "fr"): {"hello": "Salut {name}"}}
    second, changed = service.bundle("core", FR)
    assert second["hello"] == "Salut {name}" and changed != version
    assert service.bundle("core", FR)[1] == changed  # stable hash


def test_plugin_catalogs() -> None:
    plugins = PluginCatalogs()
    plugins.register(
        "radio", {"en": {"plugin.radio": {"title": "Radio"}}, "fr": {"plugin.radio": {"title": "Radio FR"}}}
    )
    with pytest.raises(PluginCatalogError, match="outside"):
        plugins.register("evil", {"en": {"core": {"hello": "pwned"}}})  # cannot override portal strings
    with pytest.raises(PluginCatalogError):
        plugins.register("broken", {"en": {"plugin.broken": {"x": "{count, plural, one {#}}"}}})
    service = CatalogService(None, locales_dir=Path("/nonexistent"), plugins=plugins)  # type: ignore[arg-type]
    assert service.t("title", FR, namespace="plugin.radio") == "Radio FR"
    de = LocaleContext(language="de", locale="de", fallback_chain=("en",))
    assert (
        service.t("title", de, namespace="plugin.radio") == "Radio"
    )  # missing plugin translation falls back
    assert plugins.unregister("plugin:radio") == 1
    assert service.t("title", FR, namespace="plugin.radio") == "title"


async def test_disabled_plugin_catalogs_are_withdrawn() -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from uuid import uuid4

    from portalab.modules.i18n.events import plugin_state_consumer

    plugins = PluginCatalogs()
    plugins.register("radio", {"en": {"plugin.radio": {"title": "Radio"}}})
    consumer = plugin_state_consumer(plugins)
    now = datetime(2026, 10, 2, tzinfo=UTC)

    def envelope(state: str) -> SimpleNamespace:
        return SimpleNamespace(
            event_id=uuid4(),
            type="plugin.state_changed",
            occurred_at=now,
            payload={"plugin_id": "radio", "state": state},
        )

    await consumer.handler(envelope("enabled"), None)  # type: ignore[arg-type]
    assert plugins.namespaces() == {"plugin.radio"}
    await consumer.handler(envelope("disabled"), None)  # type: ignore[arg-type]
    assert plugins.namespaces() == set()
