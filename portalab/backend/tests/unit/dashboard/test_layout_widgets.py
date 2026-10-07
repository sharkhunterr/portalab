"""027 — layout widgets (progress across and upright, separator, clock, note, countdown) are drawn from
their settings; a note without text or a countdown without a date asks to be set up; the frame's own
display settings (no title, no box, hide when empty) are true/false and never part of a widget's schema."""

from uuid import uuid4

from portalab.capabilities.dashboard import RegisteredWidget, WidgetDefinition, WidgetRegistry
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.modules.dashboard.gateway.gateway import config_errors, resolved_config
from portalab.modules.dashboard.widgets.builtin import (
    COUNTDOWN,
    NOTE,
    PROGRESS,
    PROGRESS_VERTICAL,
    SEPARATOR,
    SettingsProvider,
)

ME = Principal(user_id=uuid4())
CTX = LocaleContext()


def _registered(definition: WidgetDefinition) -> RegisteredWidget:
    registry = WidgetRegistry()
    registry.register(definition, SettingsProvider(definition.key), owner="module:dashboard")
    found = registry.get(definition.key)
    assert found is not None
    return found


async def test_drawn_from_settings_and_asking_to_be_set_up() -> None:
    progress = await SettingsProvider(PROGRESS.key).load(ME, {"metric": "objectives", "_no_box": True}, CTX)
    assert progress.state == "available" and progress.data == {"metric": "objectives"}
    assert (await SettingsProvider(NOTE.key).load(ME, {"text": "  "}, CTX)).state == "no-data"
    assert (await SettingsProvider(NOTE.key).load(ME, {"text": "Hi"}, CTX)).state == "available"
    assert (await SettingsProvider(COUNTDOWN.key).load(ME, {"date": ""}, CTX)).state == "no-data"
    assert PROGRESS_VERTICAL.size.default.h > PROGRESS_VERTICAL.size.default.w  # upright


def test_frame_settings_and_defaults() -> None:
    separator = _registered(SEPARATOR)
    merged, invalid = resolved_config(separator, {"style": "dotted"})
    assert not invalid and merged["_hide_title"] is True and merged["_no_box"] is True  # raw by default
    assert config_errors(separator, {"style": "line", "_hide_title": False, "_no_box": False}) == []
    assert config_errors(separator, {"_no_box": "yes"}) == ["_no_box must be true or false"]
    countdown = _registered(COUNTDOWN)
    assert config_errors(countdown, {"date": "2026-12-24"}) == []
    assert config_errors(countdown, {"date": "next week"})  # a date or nothing
