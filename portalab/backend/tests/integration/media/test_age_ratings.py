"""Issue 478 — a title's classification in full on its page: every release's rating (cinema, TV, platforms),
the household's rule « home viewing first » (a film « tous publics » at the cinema, -12 on TV, is held to 12),
and the CNC's decision for a film (its visa found by the number TMDB names, else by title and year)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.household.rules import RestrictionSettings
from portalab.modules.media.models import MediaObject, ObjectMetadata
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

RELEASES = [
    {
        "country": "FR",
        "type": "cinema",
        "certification": "TP",
        "note": "Visa CNC 142250",
        "date": "2015-05-14",
    },
    {"country": "FR", "type": "digital", "certification": "16", "note": "Netflix"},
    {"country": "FR", "type": "tv", "certification": "12", "note": "Novo19", "descriptors": ["violence"]},
    {"country": "US", "type": "cinema", "certification": "R"},
]


async def _film(media: MediaHarness) -> UUID:
    await media.configure("i18n.defaultLanguage", "fr")  # a portal rating as France (issue 438)
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert([library_record("m1", title="Mad Max : Fury Road", year=2015)], one)
    async with media.database.unit_of_work() as uow:
        object_id = (await uow.session.execute(select(MediaObject.id))).scalar_one()
        uow.session.add(
            ObjectMetadata(
                object_id=object_id,
                provider="tmdb",
                status="found",
                language="fr",
                data={
                    "title": "Mad Max : Fury Road",
                    "original_title": "Mad Max: Fury Road",
                    "release_date": "2015-05-13",
                    "certification": "TP",
                    "certifications": {"FR": "TP", "US": "R"},
                    "releases": RELEASES,
                    "_v": 4,
                },
                fetched_at=datetime(2026, 11, 16, tzinfo=UTC),
            )
        )
    await media.module.cnc.store(
        [
            {
                "visa": 142250,
                "title": "Mad Max : Fury road",
                "key": "madmaxfuryroad",
                "year": 2015,
                "direction": "George Miller",
                "decision": "Avertissement",
            }
        ]
    )
    return object_id


async def test_a_films_page_tells_its_classification_in_full(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "zoe")
    film = await _film(media)
    await login(client, "zoe")
    rating: dict[str, Any] = (await client.get(f"/api/v1/media/{film}")).json()["age_rating"]
    assert rating["age"] == 12 and rating["basis"] == "tv"  # held to its TV rating, not the cinema's « TP »
    assert {(r["country"], r["type"], r["certification"], r["age"]) for r in rating["releases"]} == {
        ("FR", "cinema", "TP", 0),
        ("FR", "digital", "16", 16),
        ("FR", "tv", "12", 12),
        ("US", "cinema", "R", 17),
    }
    tv = next(r for r in rating["releases"] if r["type"] == "tv")
    assert tv["note"] == "Novo19" and tv["descriptors"] == ["violence"]
    assert rating["cnc"] == {
        "visa": 142250,
        "decision": "Avertissement",
        "warning": True,
        "title": "Mad Max : Fury road",
        "year": 2015,
    }


async def test_the_cnc_visa_is_found_by_title_and_year_too(media: MediaHarness) -> None:
    await _film(media)
    found = await media.module.cnc.find([None], ["Mad Max: Fury Road"], 2016)  # a year off: still it
    assert found is not None and found.visa == 142250
    assert await media.module.cnc.find([], ["Mad Max: Fury Road"], 2020) is None


async def test_a_child_profile_is_held_to_the_tv_rating(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    film = await _film(media)
    owner = Principal(user_id=people["zoe"])
    created = await app.state.household_module.service.create(
        owner, display_name="Léa", kind="child", color=None, pin=None
    )
    lea_id = UUID(str(created["id"]))
    lea = Principal(user_id=lea_id, profile_of=people["zoe"])
    for age, held in ((10, True), (12, False)):
        await app.state.household_module.service.change(
            owner, lea_id, restrictions=RestrictionSettings(max_age=age, allow_unrated=True, genres=[])
        )
        media.module.gate.forget()
        # « tous publics » at the cinema would have opened it to any child: the TV's -12 holds a 10-year-old
        assert (film in await media.module.gate.blocked(lea)) is held, age
