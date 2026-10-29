"""#272: a poster changed at the source (its reference carries its version) is fetched again, and the
browser, asking by the image's tag, gets the new one — or a 304 while it is the same."""

import io

import httpx
from fastapi import FastAPI
from PIL import Image as PILImage
from sqlalchemy import select

from portalab.capabilities.media.testkit import PNG_1PX, library_record
from portalab.modules.media.models import MediaObject
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


def red_png() -> bytes:
    out = io.BytesIO()
    PILImage.new("RGB", (2, 3), (178, 7, 16)).save(out, format="PNG")
    return out.getvalue()


async def test_a_changed_poster_is_fetched_again(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "alex")
    one = media.service(1)
    library = media.library(one)
    library.images["843668:1"], library.images["843668:2"] = PNG_1PX, red_png()
    await media.module.library.upsert(
        [library_record("843668", title="Ce soir je dors chez toi", image="843668:1")], one
    )
    async with media.database.session() as session:
        object_id = (await session.execute(select(MediaObject.id))).scalar_one()
    assert await media.module.images.fetch(object_id)
    assert not await media.module.images.fetch(object_id)  # the same version: nothing to fetch

    await login(client, "alex")
    image_id = (await client.get(f"/api/v1/media/{object_id}")).json()["image_id"]
    first = await client.get(f"/api/v1/media/images/{image_id}")
    assert first.status_code == 200 and first.headers["etag"]
    assert "max-age=3600" in first.headers["cache-control"]
    same = await client.get(
        f"/api/v1/media/images/{image_id}", headers={"If-None-Match": first.headers["etag"]}
    )
    assert same.status_code == 304 and not same.content

    # the poster changed at the source: a new version, fetched again under the same address
    await media.module.library.upsert(
        [library_record("843668", title="Ce soir je dors chez toi", image="843668:2")], one
    )
    assert await media.module.images.fetch(object_id)
    assert (await client.get(f"/api/v1/media/{object_id}")).json()["image_id"] == image_id
    fresh = await client.get(
        f"/api/v1/media/images/{image_id}", headers={"If-None-Match": first.headers["etag"]}
    )
    assert fresh.status_code == 200 and fresh.headers["etag"] != first.headers["etag"]
    with PILImage.open(io.BytesIO(fresh.content)) as poster:
        assert poster.size == (2, 3)
