"""media — what the search reads of a title (#92)

``media.objects.search_text``: the title, its original title and its series, and the people behind it
(authors, narrators, directors, cast — the library's and the metadata provider's), folded the way a query is
(lower case, no accents, apostrophes, dashes and underscores turned to spaces), behind a trigram index: every
word of a query must be found there, as a substring or — for a word of four letters or more — a close
spelling (``assasin`` finds ``assassin``). Kept up to date by the database itself: a title's fields
(``title``, ``effective``) and its metadata (``object_metadata``) recompute it.

``media.credits``: who is behind each title and as what (``author``, ``narrator``, ``director``, ``writer``,
``creator``, ``cast``, ``artist``) — from the library's own fields and from the metadata provider's people
(with their portrait) — so a person is found by name and has a page of their titles. Kept up to date by the
database too, from the same two sources.

Revision ID: media_0008
Revises: media_0007
Create Date: 2026-12-13 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0008"
down_revision: str | Sequence[str] | None = "media_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# what separates words: blanks, ASCII punctuation (the apostrophe, the dash, the underscore…), and the
# typographic ones (U+00A0 to U+00BF, U+2010 to U+206F: quotes, guillemets, dashes, ellipsis)
SEPARATORS = r"[\s\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e\u00a0-\u00bf\u2010-\u206f]+"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        f"""
        CREATE FUNCTION media.search_fold(value text) RETURNS text
        LANGUAGE sql STABLE PARALLEL SAFE SET search_path = public, pg_catalog AS $$
          SELECT trim(regexp_replace(unaccent(lower(coalesce(value, ''))), '{SEPARATORS}', ' ', 'g'))
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION media.search_names(value jsonb) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
          SELECT string_agg(
            CASE jsonb_typeof(item) WHEN 'string' THEN item #>> '{}' ELSE item ->> 'name' END, ' ')
          FROM jsonb_array_elements(CASE jsonb_typeof(value) WHEN 'array' THEN value ELSE '[]'::jsonb END) item
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION media.search_text_of(object_id uuid, title text, effective jsonb) RETURNS text
        LANGUAGE sql STABLE AS $$
          SELECT left(media.search_fold(concat_ws(' ',
            title,
            effective ->> 'original_title',
            effective ->> 'series',
            media.search_names(effective -> 'authors'),
            media.search_names(effective -> 'narrators'),
            media.search_names(effective -> 'directors'),
            media.search_names(effective -> 'people'),
            (SELECT media.search_names(m.data -> 'people') FROM media.object_metadata m
              WHERE m.object_id = search_text_of.object_id AND m.status = 'found')
          )), 8000)
        $$
        """
    )
    op.execute("ALTER TABLE media.objects ADD COLUMN search_text text NOT NULL DEFAULT ''")
    op.execute(
        """
        CREATE FUNCTION media.objects_search_text() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.search_text := media.search_text_of(NEW.id, NEW.title, NEW.effective);
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER objects_search_text BEFORE INSERT OR UPDATE OF title, effective ON media.objects
        FOR EACH ROW EXECUTE FUNCTION media.objects_search_text()
        """
    )
    op.execute(
        """
        CREATE FUNCTION media.metadata_search_text() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          UPDATE media.objects o SET search_text = media.search_text_of(o.id, o.title, o.effective)
          WHERE o.id = NEW.object_id;
          RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER object_metadata_search_text AFTER INSERT OR UPDATE OF status, data
        ON media.object_metadata FOR EACH ROW EXECUTE FUNCTION media.metadata_search_text()
        """
    )
    op.execute("UPDATE media.objects SET search_text = media.search_text_of(id, title, effective)")
    op.execute(
        "CREATE INDEX ix_objects_search_text ON media.objects USING gin (search_text public.gin_trgm_ops)"
    )
    _credits()


def _credits() -> None:
    op.create_table(
        "credits",
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("image", sa.String(length=300), nullable=True),
        sa.Column("folded", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("source IN ('library', 'metadata')", name="ck_credits_source"),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["media.objects.id"],
            name="fk_credits_object_id_objects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("object_id", "source", "name", "role", name="pk_credits"),
        schema="media",
    )
    op.create_index("ix_credits_name", "credits", ["name"], schema="media")
    op.execute("CREATE INDEX ix_credits_folded ON media.credits USING gin (folded public.gin_trgm_ops)")
    # the library's own fields: authors, narrators, directors, then the people of the title (the cast of a
    # film, the authors of a book that tells no more, the artists of an album; a game's studios are not people)
    op.execute(
        """
        CREATE FUNCTION media.library_credits(object_id uuid, kind text, effective jsonb) RETURNS void
        LANGUAGE sql AS $$
          DELETE FROM media.credits c WHERE c.object_id = library_credits.object_id AND c.source = 'library';
          INSERT INTO media.credits (object_id, source, name, role, image, folded, position)
          SELECT library_credits.object_id, 'library', named.name, named.role, NULL,
                 media.search_fold(named.name), min(named.position)
          FROM (
            SELECT left(trim(CASE jsonb_typeof(item) WHEN 'string' THEN item #>> '{}'
                                  ELSE item ->> 'name' END), 200) AS name,
                   lists.role, lists.base + ordinality::int AS position
            FROM (VALUES
              ('author', 0, effective -> 'authors'),
              ('narrator', 1000, effective -> 'narrators'),
              ('director', 2000, effective -> 'directors'),
              (CASE
                 WHEN kind IN ('book', 'audiobook') AND jsonb_typeof(effective -> 'authors') = 'array'
                   AND jsonb_array_length(effective -> 'authors') > 0 THEN NULL
                 WHEN kind IN ('book', 'audiobook') THEN 'author'
                 WHEN kind IN ('movie', 'series', 'season', 'episode', 'live') THEN 'cast'
                 WHEN kind IN ('album', 'track') THEN 'artist'
               END, 3000, effective -> 'people')
            ) AS lists(role, base, list),
            jsonb_array_elements(CASE jsonb_typeof(lists.list) WHEN 'array' THEN lists.list ELSE '[]'::jsonb END)
              WITH ORDINALITY AS items(item, ordinality)
            WHERE lists.role IS NOT NULL
          ) AS named
          WHERE coalesce(named.name, '') <> ''
            AND NOT (named.role = 'cast' AND coalesce(effective -> 'directors', '[]'::jsonb) @> to_jsonb(named.name))
          GROUP BY named.name, named.role
        $$
        """
    )
    # the metadata provider's people (TMDB…): the cast, the directors, the writers, the creators
    op.execute(
        """
        CREATE FUNCTION media.metadata_credits(object_id uuid) RETURNS void LANGUAGE sql AS $$
          DELETE FROM media.credits c WHERE c.object_id = metadata_credits.object_id AND c.source = 'metadata';
          INSERT INTO media.credits (object_id, source, name, role, image, folded, position)
          SELECT metadata_credits.object_id, 'metadata', named.name, named.role, max(named.image),
                 media.search_fold(named.name), min(named.position)
          FROM (
            SELECT left(trim(p ->> 'name'), 200) AS name,
                   CASE p ->> 'department' WHEN 'cast' THEN 'cast' WHEN 'directing' THEN 'director'
                     WHEN 'writing' THEN 'writer' WHEN 'creator' THEN 'creator' END AS role,
                   left(nullif(p ->> 'image', ''), 300) AS image, ordinality::int AS position
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
    )
    op.execute(
        """
        CREATE FUNCTION media.objects_credits() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM media.library_credits(NEW.id, NEW.kind, NEW.effective);
          RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER objects_credits AFTER INSERT OR UPDATE OF kind, effective ON media.objects
        FOR EACH ROW EXECUTE FUNCTION media.objects_credits()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION media.metadata_search_text() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          UPDATE media.objects o SET search_text = media.search_text_of(o.id, o.title, o.effective)
          WHERE o.id = NEW.object_id;
          PERFORM media.metadata_credits(NEW.object_id);
          RETURN NULL;
        END
        $$
        """
    )
    op.execute("SELECT media.library_credits(id, kind, effective) FROM media.objects")
    op.execute("SELECT media.metadata_credits(object_id) FROM media.object_metadata WHERE status = 'found'")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS objects_credits ON media.objects")
    op.execute("DROP TABLE IF EXISTS media.credits")
    op.execute("DROP FUNCTION IF EXISTS media.objects_credits()")
    op.execute("DROP FUNCTION IF EXISTS media.library_credits(uuid, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS media.metadata_credits(uuid)")
    op.execute("DROP TRIGGER IF EXISTS object_metadata_search_text ON media.object_metadata")
    op.execute("DROP TRIGGER IF EXISTS objects_search_text ON media.objects")
    op.execute("DROP INDEX IF EXISTS media.ix_objects_search_text")
    op.execute("ALTER TABLE media.objects DROP COLUMN IF EXISTS search_text")
    op.execute("DROP FUNCTION IF EXISTS media.metadata_search_text()")
    op.execute("DROP FUNCTION IF EXISTS media.objects_search_text()")
    op.execute("DROP FUNCTION IF EXISTS media.search_text_of(uuid, text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS media.search_names(jsonb)")
    op.execute("DROP FUNCTION IF EXISTS media.search_fold(text)")
