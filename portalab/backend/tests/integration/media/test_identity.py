"""024 T009/T010/T011 — two sources sharing a strong id are one object with per-field provenance; fuzzy
similarity only proposes a candidate; conflicting ids never merge; merge/split are reversible and logged;
a source disappearing keeps the object; series → season → episode hierarchy; the sink is idempotent,
never deletes and sanitizes payloads; field priority (settings) and Admin overrides are deterministic."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.media_core import register_media_type
from portalab.capabilities.record_sink import ServiceRef
from portalab.capabilities.record_sink_testkit import RecordSinkContractKit, StoredRecord
from portalab.core.time import FixedClock
from portalab.modules.media.settings import priority_key
from tests.integration.media.conftest import MediaHarness
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


async def objects(media: MediaHarness) -> list[tuple]:
    async with media.database.session() as session:
        return [
            tuple(r)
            for r in await session.execute(
                text(
                    "SELECT id, kind, title, year, available, status, field_provenance"
                    " FROM media.objects ORDER BY created_at, id"
                )
            )
        ]


async def test_two_sources_one_object(media: MediaHarness, clock: FixedClock) -> None:
    plex, jelly = media.service(1, "plex"), media.service(2, "jellyfin")
    await media.module.library.upsert(
        [
            library_record(
                "p1",
                title="The Matrix",
                ids={"tmdb": "603"},
                year=1999,
                overview="Plex text",
                genres=["Action"],
            )
        ],
        plex,
    )
    await media.module.library.upsert(
        [
            library_record(
                "j9", title="Matrix", ids={"tmdb": "603", "imdb": "tt0133093"}, overview="Jelly text"
            )
        ],
        jelly,
    )
    rows = await objects(media)
    assert len(rows) == 1 and rows[0][4] is True  # available
    provenance = rows[0][6]
    assert provenance["title"].startswith("jellyfin:") or provenance["title"].startswith("plex:")
    await media.configure(priority_key("movie", "title"), ["jellyfin"])
    await media.configure(priority_key("movie", "overview"), ["plex"])
    async with media.database.unit_of_work() as uow:
        await media.module.writer.refresh(uow.session, rows[0][0])
    row = (await objects(media))[0]
    assert (
        row[2] == "Matrix"
        and row[6]["title"].startswith("jellyfin:")
        and row[6]["overview"].startswith("plex:")
    )
    # an Admin override beats every source; removing it restores the priority winner
    async with media.database.unit_of_work() as uow:
        await uow.session.execute(
            text(
                "INSERT INTO media.field_candidates (object_id, field, source_system, value, observed_at) "
                "VALUES (:o, 'title', 'admin', '\"The Matrix (1999)\"', now())"
            ),
            {"o": row[0]},
        )
        await media.module.writer.refresh(uow.session, row[0])
    assert (await objects(media))[0][2] == "The Matrix (1999)"
    # removal from one source keeps the object; from both keeps it, unavailable; history is untouched
    await media.module.library.upsert([library_record("p1", removed=True)], plex)
    assert (await objects(media))[0][4] is True
    await media.module.library.deactivate(["j9"], jelly)
    final = await objects(media)
    assert len(final) == 1 and final[0][4] is False and final[0][5] == "active"
    types = [e[0] for e in await media.events()]
    assert (
        types.count("media.added") == 1 and "media.availability_changed" in types and "media.removed" in types
    )


async def test_fuzzy_candidates_conflicts_merge_split(media: MediaHarness) -> None:
    one, two = media.service(1), media.service(2)
    await media.module.library.upsert(
        [library_record("a", title="Blade Runner", year=1982, ids={"tmdb": "78"})], one
    )
    await media.module.library.upsert([library_record("b", title="Blade Runner", year=1982)], two)  # no ids
    await media.module.library.upsert(
        [library_record("c", title="Blade Runner", year=1982, ids={"tmdb": "335984"})], two
    )
    rows = await objects(media)
    assert len(rows) == 3  # fuzzy evidence never merges; different tmdb ids are different works
    async with media.database.session() as session:
        candidates = (
            await session.execute(text("SELECT object_a, object_b, state FROM media.match_candidates"))
        ).all()
    pairs = {frozenset((a, b)) for a, b, _ in candidates}
    a_id, b_id, c_id = rows[0][0], rows[1][0], rows[2][0]
    assert frozenset((a_id, b_id)) in pairs and frozenset((a_id, c_id)) not in pairs  # conflicting ids
    now = NOW + timedelta(minutes=5)
    async with media.database.unit_of_work() as uow:
        entry = await media.module.identity.merge(uow.session, a_id, b_id, now)
        await media.module.writer.refresh(uow.session, a_id)
        merge_id = entry.id
    async with media.database.session() as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM media.source_items WHERE object_id = :a"), {"a": a_id}
            )
        ).scalar_one() == 2
        assert (
            await session.execute(text("SELECT status FROM media.objects WHERE id = :b"), {"b": b_id})
        ).scalar_one() == "merged"
    # the sink keeps resolving the merged-away source item to the survivor
    await media.module.library.upsert(
        [library_record("b", title="Blade Runner", year=1982, overview="x", at=NOW)], two
    )
    async with media.database.unit_of_work() as uow:
        await media.module.identity.split(uow.session, merge_id, now)
    async with media.database.session() as session:
        restored = (
            await session.execute(
                text("SELECT status, merged_into FROM media.objects WHERE id = :b"), {"b": b_id}
            )
        ).one()
        owner = (
            await session.execute(text("SELECT object_id FROM media.source_items WHERE external_id = 'b'"))
        ).scalar_one()
        actions = (
            (await session.execute(text("SELECT action FROM media.merge_log ORDER BY created_at, action")))
            .scalars()
            .all()
        )
    assert tuple(restored) == ("active", None) and owner == b_id and sorted(actions) == ["merge", "split"]
    with pytest.raises(Exception):  # noqa: B017 — append-only log
        async with media.database.unit_of_work() as uow:
            await uow.session.execute(text("DELETE FROM media.merge_log"))


async def test_hierarchy(media: MediaHarness) -> None:
    svc = media.service(1)
    await media.module.library.upsert(
        [
            library_record("s", kind="series", title="Dark", ids={"tvdb": "334824"}),
            library_record("s1", kind="season", title="Season 1", parent="s", position=1),
            library_record("e1", kind="episode", title="Secrets", parent="s1", position=1, duration_s=3000),
        ],
        svc,
    )
    async with media.database.session() as session:
        rows = {
            r[0]: (r[1], r[2])
            for r in await session.execute(text("SELECT kind, id, parent_id FROM media.objects"))
        }
    assert rows["season"][1] == rows["series"][0] and rows["episode"][1] == rows["season"][0]
    # another source's episode without ids resolves by (parent, kind, position) once its parents match
    other = media.service(2)
    await media.module.library.upsert(
        [
            library_record("x", kind="series", title="Dark", ids={"tvdb": "334824"}),
            library_record("x1", kind="season", title="S1", parent="x", position=1),
            library_record("x1e1", kind="episode", title="Secrets", parent="x1", position=1),
        ],
        other,
    )
    async with media.database.session() as session:
        assert (await session.execute(text("SELECT count(*) FROM media.objects"))).scalar_one() == 3


class TestMediaSink(RecordSinkContractKit):
    """The 005 RecordSink contract kit run against Media's library sink."""

    harness: MediaHarness

    @pytest.fixture(autouse=True)
    def _bind(self, media: MediaHarness) -> None:
        register_media_type("item", "media:kind.item", owner="test:kit", registry=media.types)
        TestMediaSink.harness = media

    async def make_sink(self):  # type: ignore[no-untyped-def]
        return self.harness.module.library

    async def stored(self, sink, service: ServiceRef) -> dict[str, StoredRecord]:  # type: ignore[no-untyped-def]
        rows = await sink.stored_at(service)
        return {
            ext: StoredRecord(ext, service.source_system, payload, observed, active)
            for ext, (payload, observed, active) in rows.items()
        }


async def test_sink_sanitizes(media: MediaHarness) -> None:
    svc = media.service(1)
    result = await media.module.library.upsert(
        [
            library_record(
                "m",
                title="Heat",
                ids={"tmdb": "949", "bogus": "x"},
                image="https://u:pw@img.example/p.jpg?X-Plex-Token=abc",
                api_token="leak",
            ),
            library_record("bad", title=""),
            library_record("weird", kind="unknown_kind", title="?"),
        ],
        svc,
    )
    assert (result.added, result.errored) == (1, 2)
    async with media.database.session() as session:
        payload = (await session.execute(text("SELECT payload::text FROM media.source_items"))).scalar_one()
        ids = (await session.execute(text("SELECT scheme FROM media.external_ids"))).scalars().all()
    assert (
        "leak" not in payload
        and "abc" not in payload
        and "pw" not in payload
        and "img.example/p.jpg" in payload
    )
    assert ids == ["tmdb"]
