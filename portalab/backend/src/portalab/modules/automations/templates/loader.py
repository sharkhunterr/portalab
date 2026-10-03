"""Preset templates (T029): shipped JSON definitions (``backend/automations/templates``) validated against
today's registries; instantiating creates a **draft** the Admin reviews before publishing."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from portalab.core.errors import ValidationFailed

TEMPLATES_DIR = Path(__file__).resolve().parents[5] / "automations" / "templates"


@dataclass
class Template:
    key: str
    title: str
    description: str
    definition: dict[str, Any]
    valid: bool = True
    errors: list[str] = field(default_factory=list)


def load(directory: Path = TEMPLATES_DIR) -> list[Template]:
    out = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            Template(path.stem, raw.get("title", path.stem), raw.get("description", ""), raw["definition"])
        )
    return out


def checked(templates: list[Template], validate: Any) -> list[Template]:
    for template in templates:
        try:
            validate(template.definition)
        except ValidationFailed as exc:
            template.valid, template.errors = False, list(exc.extensions.get("errors", []))
    return templates
