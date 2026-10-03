"""PostgreSQL extensions used by module migrations (CD-001: ``unaccent``, ``pg_trgm``, ``btree_gist``,
optional ``pgvector``). Only allow-listed extensions may be created::

    op.execute(create_extension_ddl("btree_gist"))
"""

ALLOWED = frozenset({"unaccent", "pg_trgm", "btree_gist", "vector"})


def create_extension_ddl(name: str) -> str:
    if name not in ALLOWED:
        raise ValueError(f"extension {name!r} is not allowed")
    return f'CREATE EXTENSION IF NOT EXISTS "{name}"'
