"""Append-only tables enforced by the database (CD-005, CD-013): events, audit, ledgers, purchases.

Usage inside an Alembic revision::

    for statement in append_only_ddl("gamification", "transactions"):
        op.execute(statement)

``UPDATE``, ``DELETE`` and ``TRUNCATE`` are rejected; corrections are new rows referencing the original.
The trigger function ``core.reject_append_only_mutation()`` is created by the core migration ``core_0003``.
"""

import re

FUNCTION = "core.reject_append_only_mutation"

APPEND_ONLY_INFO = {"portalab_append_only": True}
"""``Table.info`` marker for append-only tables (``__table_args__ = (..., {"info": APPEND_ONLY_INFO})``):
the boundary tests check that such tables hold no personal-data columns (spec 021 R5)."""

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _check(identifier: str) -> str:
    if not _IDENT.fullmatch(identifier):
        raise ValueError(f"invalid SQL identifier {identifier!r}")
    return identifier


FUNCTION_DDL = f"""
CREATE OR REPLACE FUNCTION {FUNCTION}() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'append-only table %.%: % is not allowed (insert a correction row instead)',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'P0001';
END;
$$;
"""


def append_only_ddl(schema: str, table: str) -> list[str]:
    schema, table = _check(schema), _check(table)
    return [
        f'CREATE TRIGGER "{table}_append_only_row" BEFORE UPDATE OR DELETE ON "{schema}"."{table}" '
        f"FOR EACH ROW EXECUTE FUNCTION {FUNCTION}()",
        f'CREATE TRIGGER "{table}_append_only_truncate" BEFORE TRUNCATE ON "{schema}"."{table}" '
        f"FOR EACH STATEMENT EXECUTE FUNCTION {FUNCTION}()",
    ]


def drop_append_only_ddl(schema: str, table: str) -> list[str]:
    """Development downgrades only."""
    schema, table = _check(schema), _check(table)
    return [
        f'DROP TRIGGER IF EXISTS "{table}_append_only_row" ON "{schema}"."{table}"',
        f'DROP TRIGGER IF EXISTS "{table}_append_only_truncate" ON "{schema}"."{table}"',
    ]
