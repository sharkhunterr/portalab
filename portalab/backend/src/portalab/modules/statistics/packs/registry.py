"""Built-in definition packs (T007, T025): ``backend/definitions/packs/*.json`` registered by the module
(owner ``module:statistics``); domain specs ship their own packs through ``register_definition_pack``."""

import json
from pathlib import Path

from portalab.capabilities.statistics import PackRegistry

PACKS_DIR = Path(__file__).resolve().parents[5] / "definitions" / "packs"
OWNER = "module:statistics"


def register_builtin(registry: PackRegistry, directory: Path = PACKS_DIR) -> int:
    count = 0
    for path in sorted(directory.glob("*.json")):
        pack = json.loads(path.read_text(encoding="utf-8"))
        registry.register(str(pack["domain"]), pack["definitions"], owner=OWNER)
        count += 1
    return count
