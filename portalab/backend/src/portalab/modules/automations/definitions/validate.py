"""Definition validation against the registries (T004, T007, T015): known trigger (``automatable`` event
type or schedule), known leaves with known params, known actions with their required params only, no
secret-looking parameters, substitution of **declared** event attributes only, and the AI boundary — an
``ai.invoke`` output never reaches a condition, a sensitive action or an action not accepting AI text."""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.automations import ConditionRegistry
from portalab.capabilities.events import EventTypeRegistry
from portalab.core.errors import ValidationFailed
from portalab.core.permissions import PermissionRegistry
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.substitution import FIXED, references

SECRET = re.compile(r"(password|passwd|secret|token|api_?key|credential|private_key)", re.I)
INTERNAL_TRIGGER = "automation.triggered"
AI_ACTION = "ai.invoke"


def invalid(errors: list[str]) -> ValidationFailed:
    return ValidationFailed(
        "This automation is not valid.",
        code="automation.invalid_definition",
        extensions={"errors": errors[:20]},
    )


def parse(raw: Mapping[str, Any]) -> Definition:
    try:
        return Definition.model_validate(dict(raw))
    except ValidationError as exc:
        raise invalid([f"{'.'.join(map(str, e['loc']))}: {e['msg']}"[:200] for e in exc.errors()]) from exc


def effective_sensitivity(action: ActionType, permissions: PermissionRegistry) -> str:
    """The action's declared sensitivity, raised by its permission (confirmation ⇒ destructive)."""
    declared = permissions.get(action.permission)
    if action.sensitivity == "destructive" or (declared is not None and declared.requires_confirmation):
        return "destructive"
    if action.sensitivity == "sensitive" or (declared is not None and declared.sensitive):
        return "sensitive"
    return "normal"


def event_fields(types: EventTypeRegistry, event_type: str | None) -> set[str]:
    if event_type == INTERNAL_TRIGGER:
        return {"automation", "payload"}
    registered = types.get(event_type) if event_type else None
    if registered is None or registered.schema is None:
        return set()
    return set(registered.schema.model_fields)


def validate(
    raw: Mapping[str, Any],
    *,
    types: EventTypeRegistry,
    actions: ActionRegistry,
    conditions: ConditionRegistry,
    permissions: PermissionRegistry,
    max_steps: int,
) -> Definition:
    definition = parse(raw)
    errors: list[str] = []
    trigger = definition.trigger
    if trigger.kind in ("event", "relative"):
        registered = types.get(trigger.event_type or "")
        if trigger.event_type != INTERNAL_TRIGGER and (registered is None or not registered.automatable):
            errors.append(f"trigger: {trigger.event_type} is not an automatable event type")
    fields = event_fields(types, trigger.event_type)
    for item in trigger.filter:
        if item.field not in fields:
            errors.append(f"trigger.filter: undeclared attribute {item.field}")
    if trigger.kind == "relative" and trigger.reference not in fields:
        errors.append(f"trigger.reference: undeclared attribute {trigger.reference}")
    for leaf in definition.conditions.leaves() if definition.conditions else []:
        known = conditions.get(leaf.leaf or "")
        if known is None:
            errors.append(f"conditions: unknown condition {leaf.leaf}")
            continue
        unknown = sorted(set(leaf.params) - set(known.params_schema))
        if unknown:
            errors.append(f"conditions.{leaf.leaf}: unknown params {unknown}")
        if leaf.leaf == "event_field" and leaf.params.get("field") not in fields:
            errors.append("conditions.event_field: undeclared attribute")
        if any(True for _ in references(leaf.params)):
            errors.append("conditions: substitution is not allowed in conditions")
    if len(definition.steps) > max_steps:
        errors.append(f"steps: at most {max_steps}")
    ai_steps: set[str] = set()
    seen: set[str] = set()
    for step in definition.steps:
        action = actions.get(step.action)
        if action is None:
            errors.append(f"steps.{step.id}: unknown action {step.action}")
            seen.add(step.id)
            continue
        declared = set(action.params_schema)
        if declared and set(step.params) - declared:
            errors.append(f"steps.{step.id}: unknown params {sorted(set(step.params) - declared)}")
        missing = [k for k in action.required_params() if k not in step.params]
        if missing:
            errors.append(f"steps.{step.id}: missing params {missing}")
        if any(SECRET.search(str(k)) for k in step.params):
            errors.append(f"steps.{step.id}: secret-looking parameters are not allowed")
        sensitivity = effective_sensitivity(action, permissions)
        for reference in references(step.params):
            head, _, rest = reference.partition(".")
            if reference == "__invalid__":
                errors.append(f"steps.{step.id}: invalid substitution")
            elif head == "steps":
                source = rest.split(".", 1)[0]
                if source not in seen:
                    errors.append(f"steps.{step.id}: {source} is not an earlier step")
                elif source in ai_steps and (sensitivity != "normal" or not action.ai_output_allowed):
                    errors.append(f"steps.{step.id}: AI output cannot feed {step.action}")
            elif reference in FIXED or (head == "event" and rest in fields):
                continue
            else:
                errors.append(f"steps.{step.id}: undeclared reference {reference}")
        if step.action == AI_ACTION:
            ai_steps.add(step.id)
        seen.add(step.id)
    if definition.limits.dedup_key:
        for reference in references(definition.limits.dedup_key):
            if reference.startswith("steps.") or reference == "__invalid__":
                errors.append("limits.dedup_key: only event references are allowed")
    if definition.identity.kind == "system":
        for step in definition.steps:
            action = actions.get(step.action)
            if action is not None and action.permission not in definition.identity.scopes:
                errors.append(f"identity.scopes: {step.action} needs {action.permission}")
    if errors:
        raise invalid(errors)
    return definition
