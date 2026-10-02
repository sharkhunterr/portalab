"""026 T005/T025 — contract shapes; module providers satisfy the capability protocols; 020's port
adapters satisfy the reader ports."""

from dataclasses import FrozenInstanceError

import pytest

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.config import I18nPolicyReader, UserLocalePreferenceReader
from portalab.capabilities.i18n import (
    ContentLocalizerPort,
    FormatterPort,
    LocaleContext,
    LocaleResolverPort,
    MessageRendererPort,
    TimeRendererPort,
)
from portalab.modules.administration.config.ports import (
    ConfigI18nPolicyReader,
    ConfigUserLocalePreferenceReader,
)
from portalab.modules.i18n.catalog.service import CatalogService
from portalab.modules.i18n.content.localizer import ContentLocalizer
from portalab.modules.i18n.format.formatter import Formatter
from portalab.modules.i18n.resolver.resolver import LocaleResolver
from portalab.modules.i18n.time.renderer import TimeRenderer


def test_locale_context_is_immutable() -> None:
    ctx = LocaleContext()
    with pytest.raises(FrozenInstanceError):
        ctx.language = "fr"  # type: ignore[misc]
    assert set(ctx.as_dict()) == {
        "language",
        "locale",
        "time_zone",
        "direction",
        "fallback_chain",
        "hour_cycle",
        "first_day_of_week",
        "retained_language",
    }


def test_providers_satisfy_protocols() -> None:
    assert isinstance(LocaleResolver(new_registry()), LocaleResolverPort)
    assert isinstance(CatalogService(None), MessageRendererPort)  # type: ignore[arg-type]
    assert isinstance(Formatter(), FormatterPort)
    assert isinstance(TimeRenderer(), TimeRendererPort)
    assert isinstance(ContentLocalizer(None), ContentLocalizerPort)  # type: ignore[arg-type]
    assert isinstance(ConfigUserLocalePreferenceReader(None), UserLocalePreferenceReader)  # type: ignore[arg-type]
    assert isinstance(ConfigI18nPolicyReader(None), I18nPolicyReader)  # type: ignore[arg-type]
