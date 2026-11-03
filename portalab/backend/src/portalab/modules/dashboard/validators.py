"""Dynamic validation of the dashboard settings against the registered widgets (T002, T024)."""

from typing import Any

from portalab.capabilities.dashboard import CONDITION_TYPES, WidgetRegistry
from portalab.modules.dashboard.arrangement import VIEW_COLUMNS
from portalab.modules.dashboard.gateway.gateway import config_errors
from portalab.modules.dashboard.settings import POLICIES, POLICY_CLASSES, STARTER

# #347: the welcome's play gauge, from no game to all of it
PLAY_PROFILES = ("none", "progression", "collector", "full")


class DashboardValidators:
    def __init__(self, registry: WidgetRegistry) -> None:
        self.registry = registry

    def _known(self, key: str) -> bool:
        return self.registry.get(key) is not None

    async def policies(self, value: Any) -> list[str]:
        errors = []
        for key, policy in (value or {}).items():
            if not self._known(key):
                errors.append(f"unknown widget {key!r}")
                continue
            cls = policy.get("class") if isinstance(policy, dict) else None
            if cls not in POLICY_CLASSES:
                errors.append(f"{key}: class must be one of {', '.join(POLICY_CLASSES)}")
            allowed = {"class", "condition", "lockedConfig"} | (
                {"x", "y", "w", "h", "move", "resize"} if cls == "pinned" else set()
            )
            extra = set(policy) - allowed if isinstance(policy, dict) else set()
            if extra:
                errors.append(f"{key}: unknown fields {sorted(extra)}")
            if cls == "conditional":
                condition = policy.get("condition")
                if not isinstance(condition, dict) or condition.get("type") not in CONDITION_TYPES:
                    errors.append(
                        f"{key}: a conditional policy needs a condition of type {', '.join(CONDITION_TYPES)}"
                    )
            if cls == "pinned":
                place = {k: policy.get(k) for k in ("x", "y", "w", "h")}
                if any(not isinstance(v, int) or isinstance(v, bool) for v in place.values()):
                    errors.append(f"{key}: a pinned widget needs whole numbers x, y, w and h")
                elif not (place["x"] >= 0 and 1 <= place["w"] <= 12 and place["x"] + place["w"] <= 12):
                    errors.append(f"{key}: a pinned widget stays inside the 12 columns")
                elif not (place["y"] >= 0 and 1 <= place["h"] <= 12):
                    errors.append(f"{key}: a pinned widget needs a row and a height")
            for flag in ("move", "resize"):
                if flag in policy and not isinstance(policy[flag], bool):
                    errors.append(f"{key}: « {flag} » is true or false")
            if "lockedConfig" in policy and not isinstance(policy["lockedConfig"], dict):
                errors.append(f"{key}: lockedConfig must be an object")
            elif "lockedConfig" in policy and (widget := self.registry.get(key)) is not None:
                # issue 250: the settings the administrator imposes, checked as the widget's own
                merged = {**widget.definition.config_defaults, **policy["lockedConfig"]}
                errors.extend(f"{key}: {error}" for error in config_errors(widget, merged)[:5])
        return errors

    async def starter(self, value: Any) -> list[str]:
        errors = []
        for index, entry in enumerate(value or []):
            if not isinstance(entry, dict) or not self._known(str(entry.get("widget_key", ""))):
                errors.append(f"entry {index}: unknown widget")
                continue
            known = {"widget_key", "x", "y", "w", "h", "roles", "profiles", "config", "tablet", "phone"}
            extra = set(entry) - known
            if extra:
                errors.append(f"entry {index}: unknown fields {sorted(extra)}")
            # #347: the play profiles it is shown to
            profiles = entry.get("profiles", [])
            if not isinstance(profiles, list) or not set(profiles) <= set(PLAY_PROFILES):
                errors.append(f"entry {index}: « profiles » are among {', '.join(PLAY_PROFILES)}")
            # issue 250: its place on a computer, as the administrator put it (else it flows in order)
            if ("x" in entry) != ("y" in entry):
                errors.append(f"entry {index}: « x » and « y » go together")
            elif "x" in entry and not _view_place(
                {k: entry.get(k) for k in ("x", "y", "w", "h")}, VIEW_COLUMNS["desktop"]
            ):
                errors.append(f"entry {index}: « x, y, w, h » stay within 12 columns")
            # its own place on a tablet or a phone (else derived from the computer's)
            for view in ("tablet", "phone"):
                if view in entry and not _view_place(entry[view], VIEW_COLUMNS[view]):
                    errors.append(
                        f"entry {index}: « {view} » is {{x, y, w, h}} within {VIEW_COLUMNS[view]} columns"
                    )
            # 027: how it is shown (its title, its box, while empty); issue 250: and its own settings, as its
            # settings window checks them
            config = entry.get("config", {})
            widget = self.registry.get(str(entry.get("widget_key", "")))
            if not isinstance(config, dict):
                errors.append(f"entry {index}: config is an object")
            elif widget is not None:
                errors.extend(
                    f"entry {index}: {error}"
                    for error in config_errors(widget, {**widget.definition.config_defaults, **config})[:5]
                )
        return errors

    def table(self) -> dict[str, Any]:
        return {POLICIES: self.policies, STARTER: self.starter}


def _view_place(place: Any, columns: int) -> bool:
    if not isinstance(place, dict) or set(place) != {"x", "y", "w", "h"}:
        return False
    values = {k: v for k, v in place.items() if isinstance(v, int) and not isinstance(v, bool)}
    if len(values) != 4:
        return False
    x, y, w, h = values["x"], values["y"], values["w"], values["h"]
    return x >= 0 and y >= 0 and w >= 1 and h >= 1 and x + w <= columns
