"""Preferences (T016; R5, R7): effective channels of one recipient for one category =
policy ∩ preference, where

* a channel is on by default when the category lists it in ``default_channels``;
* the user's choice (``notifications.preferences[category][channel]``) applies only when the category is
  ``user_mutable`` and not locked by the admin category policy — the choice itself is never deleted;
* mandatory channels (category declaration or policy) cannot be turned off; critical **alerts** bypass
  mutes on the **portal** channel only (never e-mail opt-out, never sound-off);
* a channel disabled by policy is suppressed with reason ``policy``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from portalab.capabilities.notifications import CHANNELS, CategoryDef


@dataclass(frozen=True, slots=True)
class ChannelDecision:
    channel: str
    enabled: bool
    reason: str | None = None  # why it is off: preference | policy
    mandatory: bool = False
    locked: bool = False


def mandatory_channels(category: CategoryDef, policy: Mapping[str, Any]) -> set[str]:
    return set(category.mandatory_channels) | set((policy or {}).get("mandatory_channels") or ())


def decide(
    category: CategoryDef,
    preferences: Mapping[str, Mapping[str, bool]],
    policy: Mapping[str, Any],
    *,
    kind: str = "notification",
    priority: str = "normal",
) -> dict[str, ChannelDecision]:
    policy = policy or {}
    mandatory = mandatory_channels(category, policy)
    disabled = set(policy.get("disabled_channels") or ())
    locked = bool(policy.get("locked")) or not category.user_mutable
    chosen = (preferences or {}).get(category.key) or {}
    out: dict[str, ChannelDecision] = {}
    for channel in CHANNELS:
        if channel in mandatory:
            out[channel] = ChannelDecision(channel, True, mandatory=True, locked=True)
            continue
        if channel in disabled:
            out[channel] = ChannelDecision(channel, False, "policy", locked=True)
            continue
        default = channel in category.default_channels
        wanted = default if locked or channel not in chosen else bool(chosen[channel])
        if not wanted and channel == "portal" and kind == "alert" and priority == "critical":
            out[channel] = ChannelDecision(channel, True, locked=locked)  # critical alerts reach the portal
            continue
        out[channel] = ChannelDecision(channel, wanted, None if wanted else "preference", locked=locked)
    return out


class MandatoryChannel(ValueError):
    pass


def validate_update(
    categories: Mapping[str, CategoryDef],
    policies: Mapping[str, Mapping[str, Any]],
    update: Mapping[str, Mapping[str, bool]],
) -> None:
    """Refuse turning off a mandatory channel or touching a locked category."""
    for key, channels in update.items():
        category = categories.get(key)
        if category is None:
            raise MandatoryChannel(f"unknown category {key!r}")
        policy = policies.get(key) or {}
        mandatory = mandatory_channels(category, policy)
        for channel, enabled in channels.items():
            if channel not in CHANNELS:
                raise MandatoryChannel(f"unknown channel {channel!r}")
            if not enabled and channel in mandatory:
                raise MandatoryChannel(f"{key}/{channel} is mandatory")
