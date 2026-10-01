"""T044 — every mapped column named like personal data is classified or explicitly non-personal (CI gate)."""

import pytest

from portalab.app.composition import import_all_models
from portalab.core.db import all_metadata
from portalab.core.privacy_registry import unclassified_pii_columns
from portalab.core.tombstone import scrub_values

pytestmark = pytest.mark.boundary


def test_no_unclassified_personal_data_columns() -> None:
    import_all_models()
    offenders = [name for metadata in all_metadata() for name in unclassified_pii_columns(metadata)]
    assert offenders == [], (
        "classify these columns with pii(...) or mark them not_personal(reason): " + ", ".join(offenders)
    )


def test_every_registered_table_can_be_tombstoned() -> None:
    import_all_models()
    for metadata in all_metadata():
        for table in metadata.tables.values():
            scrub_values(table)  # raises TombstoneError for NOT NULL PII without a tombstone value
