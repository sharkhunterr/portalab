"""#275: an archive is the attacker's to write (its passphrase too) — the tables, partitions and folders its
description names are checked when it is read, before anything is emptied: no SQL rides on a partition's
bound, no folder outside the portal's data is moved or deleted."""

from typing import Any

import pytest

from portalab.modules.administration.backup.archive import FORMAT, BackupError, upgrade_manifest


def _manifest(**changes: Any) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "tables": [{"name": "health.health_samples", "rows": 1, "columns": ["id"]}],
        "partitions": [
            {
                "parent": "health.health_samples",
                "name": "health.health_samples_p202612",
                "bound": "FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00')",
            },
            {
                "parent": "events.events",
                "name": "events.events_business",
                "bound": "FOR VALUES IN ('business')",
            },
            {"parent": "audit.audit_entries", "name": "audit.audit_entries_pdefault", "bound": "DEFAULT"},
        ],
        "folders": [{"name": "blobs/avatars"}, {"name": "visuals"}],
        **changes,
    }


def test_what_portalab_writes_is_read() -> None:
    assert upgrade_manifest(_manifest())["folders"][1]["name"] == "visuals"


@pytest.mark.parametrize(
    "crafted",
    [
        {
            "partitions": [
                {"parent": "a.b", "name": "a.c", "bound": "DEFAULT; COPY (SELECT 1) TO PROGRAM 'id'"}
            ]
        },
        {
            "partitions": [
                {"parent": "a.b", "name": "a.c", "bound": "FOR VALUES IN ('x'); DROP TABLE a.b; --')"}
            ]
        },
        {"partitions": [{"parent": 'a"; DROP TABLE x; --.b', "name": "a.c", "bound": "DEFAULT"}]},
        {"tables": [{"name": 'identity"."users'}]},
        {"folders": [{"name": "../../home"}]},
        {"folders": [{"name": "/etc"}]},
        {"folders": [{"name": "blobs/../.."}]},
        {"partitions": [{"name": "a.c"}]},
    ],
)
def test_a_crafted_description_is_refused(crafted: dict[str, Any]) -> None:
    with pytest.raises(BackupError) as caught:
        upgrade_manifest(_manifest(**crafted))
    assert caught.value.code == "backup.damaged"
