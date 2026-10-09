"""027 (#12) — the « shuffle » widget: titles drawn at random among what the library holds and can show
(available, with a poster), films and series by default or one kind, each with its year, genres and
overview."""

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import Image, MediaObject
from portalab.modules.media.providers.insight_widgets import ShuffleWidget
from tests.integration.media.conftest import MediaHarness
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


async def _draw(media: MediaHarness, **config: Any) -> list[dict[str, Any]]:
    widget = ShuffleWidget(media.database, media.module.clock)
    payload = await widget.load(Principal(channel="system"), config, LocaleContext(locale="en"))
    return list((payload.data or {}).get("items") or [])


async def test_shuffle_draws_available_titles_with_a_poster(media: MediaHarness) -> None:
    plex = media.service(1, "plex")
    await media.module.library.upsert(
        [
            library_record("m1", title="Alien", year=1979, genres=["Sci-Fi", "Horror"], overview="In space."),
            library_record("m2", title="No poster", year=2001),
            library_record("s1", kind="series", title="Firefly", year=2002),
            library_record("b1", kind="book", title="Dune", year=1965),
            library_record("m3", title="Gone", year=1999),
        ],
        plex,
    )
    await media.module.library.deactivate(["m3"], plex)  # no longer in the library
    async with media.database.unit_of_work() as uow:
        objects = {o.title: o.id for o in (await uow.session.execute(select(MediaObject))).scalars()}
        for title in ("Alien", "Firefly", "Dune", "Gone"):
            uow.session.add(
                Image(
                    object_id=objects[title],
                    role="poster",
                    blob_key=str(uuid4()),
                    content_hash="x" * 64,
                    source_ref=title,
                    created_at=NOW,
                )
            )

    drawn = {card["title"]: card for card in await _draw(media)}
    assert set(drawn) == {"Alien", "Firefly"}  # films and series with a poster, still in the library
    alien = drawn["Alien"]
    assert (
        alien["year"] == 1979 and alien["genres"] == ["Sci-Fi", "Horror"] and alien["overview"] == "In space."
    )
    assert alien["image_id"] and alien["route"] == f"/media/{objects['Alien']}"
    assert {c["title"] for c in await _draw(media, kind="book")} == {"Dune"}
