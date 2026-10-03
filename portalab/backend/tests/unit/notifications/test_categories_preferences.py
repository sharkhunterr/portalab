"""010 T004/T010/T015/T031 — categories: declared, validated, owner-tagged (plugin categories namespaced and
never mandatory); preferences: policy ∩ preference per channel, mandatory channels cannot be disabled,
critical alerts bypass portal mutes only, the stored choice is kept when the policy relaxes; alerts need
priority ≥ high."""

import pytest

from portalab.capabilities.notifications import (
    CategoryDef,
    CategoryError,
    CategoryRegistry,
    CommunicationRequest,
    Users,
    declare_category,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.notifications.preferences.resolver import MandatoryChannel, decide, validate_update
from portalab.modules.notifications.producer.service import CategoryUnknown, InvalidCommunication, Producer

MEDIA = CategoryDef("media.new", "module:media", "l", default_channels=("portal",))
SECURITY = CategoryDef(
    "account.security", "module:notifications", "l", "high", ("portal", "email"), ("portal",), False
)


def test_category_registry() -> None:
    registry = CategoryRegistry()
    declare_category("media.new", "module:media", "l", registry=registry)
    declare_category("plugin:radio.tracks", "plugin:radio", "l", registry=registry)
    for bad in (
        CategoryDef("nodot", "module:x", "l"),
        CategoryDef("media.stolen", "plugin:radio", "l"),
        CategoryDef("plugin:radio.must", "plugin:radio", "l", mandatory_channels=("portal",)),
        CategoryDef("media.sms", "module:media", "l", default_channels=("sms",)),
        CategoryDef("media.new", "module:other", "l"),
    ):
        with pytest.raises(CategoryError):
            registry.declare(bad)
    assert registry.unregister("plugin:radio") == 1 and [c.key for c in registry.all()] == ["media.new"]


def test_preferences_matrix() -> None:
    assert {k: d.enabled for k, d in decide(MEDIA, {}, {}).items()} == {"portal": True, "email": False}
    muted = decide(MEDIA, {"media.new": {"portal": False, "email": True}}, {})
    assert (muted["portal"].enabled, muted["portal"].reason, muted["email"].enabled) == (
        False,
        "preference",
        True,
    )
    policy_off = decide(MEDIA, {"media.new": {"email": True}}, {"disabled_channels": ["email"]})
    assert policy_off["email"].reason == "policy"
    relaxed = decide(MEDIA, {"media.new": {"email": True}}, {})
    assert relaxed["email"].enabled  # the stored choice was kept and applies again
    forced = decide(MEDIA, {"media.new": {"portal": False}}, {"mandatory_channels": ["portal"]})
    assert forced["portal"].enabled and forced["portal"].mandatory
    security = decide(SECURITY, {"account.security": {"portal": False, "email": False}}, {})
    assert security["portal"].enabled and security["email"].enabled  # not user mutable: defaults apply
    critical = decide(
        MEDIA, {"media.new": {"portal": False, "email": False}}, {}, kind="alert", priority="critical"
    )
    assert critical["portal"].enabled and not critical["email"].enabled  # bypass on the portal only
    with pytest.raises(MandatoryChannel):
        validate_update({"account.security": SECURITY}, {}, {"account.security": {"portal": False}})
    validate_update({"media.new": MEDIA}, {}, {"media.new": {"portal": False}})


def test_request_validation() -> None:
    registry = CategoryRegistry()
    registry.declare(MEDIA)
    producer = Producer(None, None, None, CapabilityRegistry(), registry, None)  # type: ignore[arg-type]
    base = {"category": "media.new", "template_key": "media:new", "audience": Users(()), "dedup_key": "k"}
    producer.validate(CommunicationRequest(**base))  # type: ignore[arg-type]
    with pytest.raises(CategoryUnknown):
        producer.validate(CommunicationRequest(**{**base, "category": "nope.x"}))  # type: ignore[arg-type]
    for change in (
        {"kind": "alert", "priority": "normal"},
        {"params": {"api_token": "s3cr3t"}},
        {"template_key": "nonamespace"},
        {"action_url": "https://evil.example"},
        {"dedup_key": " "},
    ):
        with pytest.raises(InvalidCommunication):
            producer.validate(CommunicationRequest(**{**base, **change}))  # type: ignore[arg-type]
