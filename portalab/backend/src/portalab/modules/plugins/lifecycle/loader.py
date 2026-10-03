"""Code loading (Tier 2, R6): a plugin package's entry point ``module:function`` is imported from its
installed directory. Python cannot reliably unload modules, so the first load of new code — and every
update — happens at a (graceful) restart: ``loaded(...)`` tells whether this process already runs that
exact version."""

import contextlib
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _module_name(entry_point: str) -> str:
    return entry_point.split(":", 1)[0]


def loaded_from(entry_point: str) -> Path | None:
    module = sys.modules.get(_module_name(entry_point).split(".")[0])
    file = getattr(module, "__file__", None)
    return Path(file).resolve().parent if file else None


def loaded(entry_point: str, package: Path) -> bool:
    origin = loaded_from(entry_point)
    return origin is not None and package.resolve() in (origin, *origin.parents)


def forget(entry_point: str) -> None:
    """Drop every module of the plugin's package from the import cache (a version switch at restart)."""
    root = _module_name(entry_point).split(".")[0]
    for name in [n for n in sys.modules if n == root or n.startswith(f"{root}.")]:
        del sys.modules[name]


def load(entry_point: str, package: Path) -> Callable[[Any], Any]:
    """Import ``module:function`` from ``package``. When another version of the plugin's code is cached,
    it is forgotten first: objects created by the old code may live on until the process restarts, which
    is why updates are completed by a restart."""
    module_name, function = entry_point.split(":", 1)
    if loaded_from(entry_point) is not None and not loaded(entry_point, package):
        forget(entry_point)
    sys.path.insert(0, str(package))
    try:
        module = importlib.import_module(module_name)
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(package))
    register = getattr(module, function, None)
    if not callable(register):
        raise RuntimeError(f"entry point {entry_point!r} is not callable")
    return register  # type: ignore[no-any-return]
