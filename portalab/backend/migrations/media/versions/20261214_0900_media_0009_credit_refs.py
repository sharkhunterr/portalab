"""media — the metadata provider's id of each person credited (#92)

``media.credits.ref``: the person's id at the metadata provider (TMDB), so their page can show what the
provider knows of them — biography, birth, every title of theirs and which the library has.

Revision ID: media_0009
Revises: media_0008
Create Date: 2026-12-14 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0009"
down_revision: str | Sequence[str] | None = "media_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION = """
        CREATE OR REPLACE FUNCTION media.metadata_credits(object_id uuid) RETURNS void LANGUAGE sql AS $$
          DELETE FROM media.credits c WHERE c.object_id = metadata_credits.object_id AND c.source = 'metadata';
          INSERT INTO media.credits (object_id, source, name, role, image, folded, position, ref)
          SELECT metadata_credits.object_id, 'metadata', named.name, named.role, max(named.image),
                 media.search_fold(named.name), min(named.position), max(named.ref)
          FROM (
            SELECT left(trim(p ->> 'name'), 200) AS name,
                   CASE p ->> 'department' WHEN 'cast' THEN 'cast' WHEN 'directing' THEN 'director'
                     WHEN 'writing' THEN 'writer' WHEN 'creator' THEN 'creator' END AS role,
                   left(nullif(p ->> 'image', ''), 300) AS image, ordinality::int AS position,
                   left(nullif(p -> 'ids' ->> 'tmdb', ''), 40) AS ref
            FROM media.object_metadata m,
                 jsonb_array_elements(CASE jsonb_typeof(m.data -> 'people') WHEN 'array'
                                      THEN m.data -> 'people' ELSE '[]'::jsonb END) WITH ORDINALITY AS e(p, ordinality)
            WHERE m.object_id = metadata_credits.object_id AND m.status = 'found'
              AND jsonb_typeof(p) = 'object'
          ) AS named
          WHERE coalesce(named.name, '') <> '' AND named.role IS NOT NULL
          GROUP BY named.name, named.role
        $$
        """
# before this revision: the same, without the person's id
PREVIOUS = (
    FUNCTION.replace(", position, ref)", ", position)")
    .replace(", min(named.position), max(named.ref)", ", min(named.position)")
    .replace(
        ",\n                   left(nullif(p -> 'ids' ->> 'tmdb', ''), 40) AS ref",
        "",
    )
)


def upgrade() -> None:
    op.add_column("credits", sa.Column("ref", sa.String(length=40), nullable=True), schema="media")
    op.execute(FUNCTION)
    op.execute("SELECT media.metadata_credits(object_id) FROM media.object_metadata WHERE status = 'found'")


def downgrade() -> None:
    op.execute(PREVIOUS)
    op.drop_column("credits", "ref", schema="media")
