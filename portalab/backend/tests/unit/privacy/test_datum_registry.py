"""021 T039 (F19) — modules register datum classes; plugins declaring personal data need an erasure
participant."""

import pytest

from portalab.capabilities.visibility import DatumClassError, DatumClassRegistry
from portalab.modules.privacy.plugins import PluginPrivacyError, check_plugin_personal_data

pytestmark = pytest.mark.unit


def test_register_and_unregister_owner() -> None:
    registry = DatumClassRegistry()
    for key in ("progression", "media_history", "member_listing", "community_activity", "projects", "votes"):
        registry.register(key, owner=f"module:{key}", classification="activity")
    assert {datum.key for datum in registry.all()} >= {"progression", "votes"}
    with pytest.raises(DatumClassError):
        registry.register("votes", owner="module:other", classification="personal")
    assert registry.unregister("module:votes") == 1


def test_plugins_with_personal_data_need_an_erasure_participant() -> None:
    check_plugin_personal_data("plugin:weather", declares_personal_data=False, has_erasure_participant=False)
    check_plugin_personal_data("plugin:diary", declares_personal_data=True, has_erasure_participant=True)
    with pytest.raises(PluginPrivacyError):
        check_plugin_personal_data("plugin:diary", declares_personal_data=True, has_erasure_participant=False)
