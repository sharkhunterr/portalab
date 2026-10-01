"""Composition root helpers: discover modules, their models and their migration locations.

Only ``app`` may import everything (contracts/module-boundaries.md rule 5).
"""

import importlib
import pkgutil
from pathlib import Path

import portalab.modules

BACKEND_DIR = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = BACKEND_DIR / "migrations"

KERNEL_MODEL_MODULES: tuple[str, ...] = ("portalab.core.jobs.models", "portalab.core.live")


def module_names() -> list[str]:
    """First-party module packages present under ``portalab.modules`` (sorted, deterministic)."""
    return sorted(info.name for info in pkgutil.iter_modules(portalab.modules.__path__) if info.ispkg)


def import_all_models() -> None:
    """Import kernel and module ORM models so their metadata is registered."""
    for dotted in KERNEL_MODEL_MODULES:
        importlib.import_module(dotted)
    for name in module_names():
        try:
            importlib.import_module(f"portalab.modules.{name}.models")
        except ModuleNotFoundError as exc:
            if exc.name != f"portalab.modules.{name}.models":
                raise


def migration_locations() -> list[str]:
    """Core versions directory + every ``migrations/<module>/versions`` directory (module-contributed)."""
    locations = [str(MIGRATIONS_DIR / "versions")]
    for child in sorted(MIGRATIONS_DIR.iterdir()):
        versions = child / "versions"
        if child.is_dir() and child.name != "versions" and versions.is_dir():
            locations.append(str(versions))
    return locations
