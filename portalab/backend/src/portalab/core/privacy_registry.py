"""Personal-data classification registry (data-model.md §3, CD-016).

Columns holding personal data declare their class through SQLAlchemy column ``info``::

    email: Mapped[str | None] = mapped_column(String(320), info=pii("contact"))
    display_name: Mapped[str] = mapped_column(String(64), info=pii("profile", tombstone="deleted-user"))
    service_name: Mapped[str] = mapped_column(String(64), info=not_personal("service label"))

Privacy (spec 021) walks this registry generically for export, erasure (tombstone) and retention, instead of
hard-coding table names. A CI test fails when a column *named like* personal data is left unclassified.
"""

import re
from typing import Any, Literal, cast, get_args

from sqlalchemy import MetaData, Table

Classification = Literal["identifier", "contact", "profile", "preference", "activity", "content", "technical"]
CLASSIFICATIONS: tuple[str, ...] = get_args(Classification)

PII_KEY = "portalab_pii"
TOMBSTONE_KEY = "portalab_tombstone"
NON_PERSONAL_KEY = "portalab_non_personal"

_PII_NAME = re.compile(
    r"(^|_)(e?mail|email_address|name|first_name|last_name|full_name|display_name|username|nickname|"
    r"phone|mobile|address|street|city|postcode|zip|birth\w*|dob|ip|ip_address|user_agent|token|"
    r"password|avatar|location|latitude|longitude|geo)($|_)",
    re.IGNORECASE,
)


def pii(classification: Classification, *, tombstone: Any = None) -> dict[str, Any]:
    """Column ``info`` for personal data; ``tombstone`` is the value used when the column is NOT NULL."""
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unknown personal-data classification {classification!r}")
    info: dict[str, Any] = {PII_KEY: classification}
    if tombstone is not None:
        info[TOMBSTONE_KEY] = tombstone
    return info


def not_personal(reason: str) -> dict[str, Any]:
    """Column ``info`` explicitly stating that a PII-looking column holds no personal data."""
    if not reason.strip():
        raise ValueError("not_personal() requires a reason")
    return {NON_PERSONAL_KEY: reason.strip()}


def _table(model_or_table: Any) -> Table:
    table = getattr(model_or_table, "__table__", model_or_table)
    if not isinstance(table, Table):
        raise TypeError(f"expected a mapped model or Table, got {type(model_or_table).__name__}")
    return table


def personal_columns(model_or_table: Any) -> dict[str, Classification]:
    """``{column_name: classification}`` for every classified personal-data column."""
    table = _table(model_or_table)
    return {
        column.name: cast(Classification, column.info[PII_KEY])
        for column in table.columns
        if PII_KEY in column.info
    }


def tombstone_value(model_or_table: Any, column_name: str) -> Any:
    return _table(model_or_table).columns[column_name].info.get(TOMBSTONE_KEY)


def looks_personal(column_name: str) -> bool:
    return bool(_PII_NAME.search(column_name))


def unclassified_pii_columns(metadata: MetaData) -> list[str]:
    """Columns named like personal data that are neither classified nor marked non-personal."""
    offenders: list[str] = []
    for table in metadata.tables.values():
        for column in table.columns:
            if PII_KEY in column.info or NON_PERSONAL_KEY in column.info:
                continue
            if looks_personal(column.name):
                offenders.append(f"{table.fullname}.{column.name}")
    return offenders
