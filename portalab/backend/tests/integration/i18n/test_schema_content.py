"""026 T006/T029/T030 — schema constraints; source content versions immutable; translations are new
versions; fallback flagged; external content keeps its source and provenance."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.capabilities.i18n import LocaleContext, Translation
from portalab.core.db import Database
from portalab.modules.i18n.content.external import present
from tests.integration.i18n.conftest import I18nHarness


async def test_unique_entry_and_language_fk(database: Database) -> None:
    insert = text(
        "INSERT INTO i18n.catalog_entries (id, namespace, key, language, message, state, catalog_version, "
        "updated_at) VALUES (:id, 'core', 'k', :lang, 'm', 'published', 1, now())"
    )
    async with database.engine.begin() as conn:
        await conn.execute(insert, {"id": uuid4(), "lang": "fr"})
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4(), "lang": "fr"})
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4(), "lang": "xx"})  # unknown language
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(text("DELETE FROM i18n.languages WHERE code = 'fr'"))  # referenced


async def test_content_versions(i18n: I18nHarness) -> None:
    content = i18n.module.content
    assert await content.register_version("news", "n1", "fr", state="source", source_language="fr") == 1
    fr_ctx = LocaleContext(language="fr", fallback_chain=("en",))
    en_ctx = LocaleContext(language="en", fallback_chain=())
    found = await content.get("news", "n1", en_ctx)
    assert found is not None and found.language == "fr" and found.is_fallback and found.state == "source"
    await content.register_version(
        "news", "n1", "en", state="translated", source_language="fr", translation_of_version=1
    )
    translated = await content.get("news", "n1", en_ctx)
    assert translated is not None and translated.language == "en" and not translated.is_fallback
    assert (await content.get("news", "n1", fr_ctx)).state == "source"  # type: ignore[union-attr]
    with pytest.raises(DBAPIError, match="immutable"):
        async with i18n.full.database.engine.begin() as conn:
            await conn.execute(
                text("UPDATE i18n.localized_content_versions SET state = 'translated' WHERE state = 'source'")
            )


class FakeTranslator:
    async def translate(self, text: str, source_language: str | None, target_language: str) -> Translation:
        return Translation(f"[{target_language}] {text}", target_language, "fake")


async def test_external_content() -> None:
    ctx = LocaleContext(language="fr")
    provenance = {"source_system": "plex", "external_id": "42"}
    as_is = await present("Hello", declared_language="en", provenance=provenance, ctx=ctx)
    assert as_is.text == "Hello" and not as_is.translated  # no provider ⇒ feature absent
    translated = await present(
        "Hello",
        declared_language="en",
        provenance=provenance,
        ctx=ctx,
        provider=FakeTranslator(),
        translate=True,
    )
    assert (
        translated.text == "[fr] Hello"
        and translated.source_text == "Hello"
        and translated.marker == "machine_translation"
    )
    assert translated.provenance == provenance
    unknown = await present("???", declared_language=None, provenance=provenance, ctx=ctx)
    hidden = await present(
        "???", declared_language=None, provenance=provenance, ctx=ctx, unknown_policy="hide"
    )
    assert unknown.text == "???" and unknown.marker == "language_unknown" and hidden.hidden
