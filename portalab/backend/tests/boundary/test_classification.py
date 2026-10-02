"""021 T005 — classification guards: append-only tables hold no personal-data columns; every PII-looking
column is classified (see test_pii_classification); retention never deletes integrity-necessary data."""

import pytest

from portalab.app.composition import import_all_models
from portalab.capabilities.retention import RetentionRegistry, RetentionTarget, RetentionTargetError
from portalab.capabilities.retention import default_retention_targets as targets
from portalab.core.db import all_metadata
from portalab.core.privacy_registry import personal_columns
from portalab.modules.privacy.retention import registry  # noqa: F401 — kernel targets

pytestmark = pytest.mark.boundary


def _append_only_tables() -> list[object]:
    import_all_models()
    return [
        table
        for metadata in all_metadata()
        for table in metadata.tables.values()
        if table.info.get("portalab_append_only")
    ]


def test_known_append_only_tables_are_flagged() -> None:
    names = {table.fullname for table in _append_only_tables()}  # type: ignore[attr-defined]
    assert {
        "identity.account_state_history",
        "audit.audit_entries",
        "audit.audit_checkpoints",
        "privacy.retention_runs",
    } <= names


def test_append_only_tables_hold_no_personal_data() -> None:
    offenders = {
        table.fullname: personal_columns(table) for table in _append_only_tables() if personal_columns(table)
    }  # type: ignore[attr-defined]
    assert offenders == {}


def test_retention_never_deletes_integrity_necessary_data() -> None:
    for target in targets.all():
        assert not (target.integrity_necessary and target.action in ("delete", "anonymize")), target.name
    with pytest.raises(RetentionTargetError):
        RetentionRegistry().register(
            RetentionTarget("ledger", "gamification.ledger", "history", "created_at", "delete", "m", True)
        )
