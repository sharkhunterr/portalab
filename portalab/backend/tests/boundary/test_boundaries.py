"""T030 — architecture boundaries as failing tests (contracts/module-boundaries.md).

* import-linter contracts run inside pytest;
* first-party modules are mutually independent (computed from the live import graph, so new modules are
  covered automatically);
* no foreign key crosses module schemas except towards ``identity.users(id)``;
* instants are ``timestamptz`` only;
* each single-owner mechanism lives in exactly one module (CANONICAL_DECISIONS §1).
"""

import shutil
import subprocess
from pathlib import Path

import grimp
import pytest

from portalab.app.composition import BACKEND_DIR, import_all_models, module_names
from portalab.core.db import all_metadata, assert_timezone_aware

pytestmark = pytest.mark.boundary

ALLOWED_CROSS_SCHEMA_TARGET = ("identity", "users")

# mechanism -> (owning module, submodule names that would indicate a competing implementation elsewhere)
SINGLE_OWNERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "configuration store": ("administration", ("config_store", "settings_store")),
    "WHEN/IF/THEN engine": ("automations", ("rules_engine", "automation_engine")),
    "event model & dedup": ("events", ("event_store", "dedup")),
    "ledger": ("gamification", ("ledger",)),
    "funding lifecycle": ("marketplace", ("funding",)),
    "incident lifecycle": ("support", ("incidents",)),
    "visibility engine": ("privacy", ("visibility",)),
    "self-observation": ("observability", ("self_observation",)),
    "localization": ("i18n", ("localization", "translations")),
}


def test_import_linter_contracts_hold() -> None:
    executable = shutil.which("lint-imports")
    assert executable, "import-linter must be installed in the dev environment"
    result = subprocess.run(  # noqa: S603 — fixed local executable and arguments
        [executable, "--config", str(BACKEND_DIR / "importlinter.ini")],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_modules_do_not_import_each_other() -> None:
    modules = module_names()
    if len(modules) < 2:
        pytest.skip("fewer than two modules yet — rule becomes active as modules are added")
    graph = grimp.build_graph("portalab")
    violations = [
        (a, b)
        for a in modules
        for b in modules
        if a != b
        and graph.chain_exists(
            importer=f"portalab.modules.{a}", imported=f"portalab.modules.{b}", as_packages=True
        )
    ]
    assert violations == [], f"modules must talk through capabilities/events only: {violations}"


def test_no_cross_schema_foreign_keys() -> None:
    import_all_models()
    violations: list[str] = []
    for metadata in all_metadata():
        for table in metadata.tables.values():
            for fk in table.foreign_keys:
                target = fk.column.table
                if (
                    target.schema != table.schema
                    and (target.schema, target.name) != ALLOWED_CROSS_SCHEMA_TARGET
                ):
                    violations.append(f"{table.fullname}.{fk.parent.name} -> {target.fullname}")
    assert violations == []


def test_datetime_columns_are_timestamptz() -> None:
    import_all_models()
    for metadata in all_metadata():
        assert_timezone_aware(metadata)


@pytest.mark.parametrize("mechanism", sorted(SINGLE_OWNERS))
def test_single_owner_mechanisms(mechanism: str) -> None:
    owner, markers = SINGLE_OWNERS[mechanism]
    modules_dir = BACKEND_DIR / "src" / "portalab" / "modules"
    offenders = []
    for module in module_names():
        if module == owner:
            continue
        for marker in markers:
            if (modules_dir / module / f"{marker}.py").exists() or (modules_dir / module / marker).is_dir():
                offenders.append(f"{module}/{marker}")
    assert offenders == [], f"{mechanism} is owned by '{owner}' only: {offenders}"
    if owner not in module_names():
        pytest.skip(f"owner module '{owner}' not implemented yet (skipped-until-present)")


def test_module_packages_are_flat_and_named_once() -> None:
    names = module_names()
    assert len(names) == len(set(names))
    for name in names:
        assert Path(BACKEND_DIR / "src" / "portalab" / "modules" / name / "__init__.py").exists()
