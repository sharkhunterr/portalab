"""Vulture false positives (CI validate:dead-code): names a signature needs but does not use (protocols,
``__exit__``). Generated with ``vulture src --min-confidence 80 --make-whitelist``."""

# ruff: noqa
target_language  # unused variable (src/portalab/capabilities/i18n/__init__.py:145)
scenario  # unused variable (src/portalab/connectors/conformance.py:39)
tb  # unused variable (src/portalab/core/db.py:125)
tb  # unused variable (src/portalab/core/metrics.py:197)
