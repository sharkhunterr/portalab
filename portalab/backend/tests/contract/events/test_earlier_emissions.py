"""007 T011 — every event type emitted by 002/003/020/021 is registered, so their emissions validate
against the store-backed publisher (no quarantine)."""

import pytest

import portalab.modules.administration.module
import portalab.modules.authz.module
import portalab.modules.identity.module
import portalab.modules.privacy.module  # noqa: F401
from portalab.capabilities.events import default_event_types
from portalab.modules.events.registry.types import validate

pytestmark = pytest.mark.contract

EMITTED = {
    "user.created": {"state": "active", "reason": "x"},
    "user.suspended": {"from_state": "active", "to_state": "suspended", "reason": "x"},
    "user.signed_in": {"session_id": "s"},
    "user.data_exported": {"export_id": "e"},
    "permission.role_assigned": {"role": "editor"},
    "permission.denied": {"permission": "users.manage", "reason": "no_grant"},
    "permission.admin_transfer_attempted": {"action": "admin.transferred", "result": "success"},
    "audit.checkpoint_created": {"from_seq": 1, "to_seq": 2, "count": 2},
    "privacy.override_applied": {"policy_id": "p", "datum_class": "profile_field", "mode": "force_private"},
    "service.data_purged": {"service_id": "plex", "rows": 3},
    "admin.config_changed": {"keys": ["identity.dormancyDays"], "change_id": "c"},
    "admin.policy_changed": {"setting": "demo.theme", "mode": "lock", "action": "applied"},
    "admin.plugin_toggled": {"kind": "plugin", "ref": "weather", "enabled": False},
}


@pytest.mark.parametrize("event_type", sorted(EMITTED))
def test_registered_and_valid(event_type: str) -> None:
    outcome = validate(default_event_types, event_type, 1, EMITTED[event_type])
    assert outcome.reason is None, outcome.detail
