"""008 T013 — semantic retrieval. Without an ``EmbeddingProvider`` (or without pgvector) semantic mode is
reported ``unavailable`` while lexical results still come back. With pgvector (``requires_pgvector``):
meaning-related matches without shared terms; candidates re-hydrated and re-authorized (forbidden and
deleted ids dropped)."""

import hashlib
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from datetime import datetime

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.search import EMBEDDING, IndexDocument
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.search.conftest import SearchHarness
from tests.unit.search.fakes import FakeProvider

pytestmark = pytest.mark.integration

TOPICS = {"film": [1.0, 0.0], "movie": [1.0, 0.0], "cinema": [0.9, 0.1], "book": [0.0, 1.0]}


class Embedder:
    model_id = "toy-2d"
    dimension = 2

    async def embed(self, texts: Sequence[str], language: str | None) -> Sequence[Sequence[float]]:
        return [next((v for word, v in TOPICS.items() if word in t.lower()), [0.5, 0.5]) for t in texts]


class Library(FakeProvider):
    async def documents(self, since: datetime | None) -> AsyncIterator[IndexDocument]:
        for index, title in enumerate(self.titles):
            yield IndexDocument(str(index), "en", title, hashlib.sha256(title.encode()).hexdigest())


async def test_semantic_unavailable_is_honest(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    search.module.config = replace(search.module.config, semantic_enabled=True)
    body = (await client.post("/api/v1/search", json={"q": "jellyfin", "mode": "semantic"})).json()
    assert body["semantic"] == "unavailable"
    assert any(i["title"] == "Jellyfin Media" for g in body["groups"] for i in g["items"])
    assert await search.module.semantic.index("services") == 0  # not Indexable: nothing to do


async def test_semantic_with_pgvector(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    if not await search.module.semantic.table_exists():
        pytest.skip("requires pgvector (search.embeddings absent)")
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    search.registry.register(Library("library", titles=("Cinema night", "Book club")), owner="module:library")
    search.registry.register(
        Library("vault", permission="audit.read", titles=("Movie secrets",)), owner="module:vault"
    )
    search.full.identity.capabilities.provide(EMBEDDING, Embedder(), instance_ref="toy", owner="module:ai")
    search.module.config = replace(search.module.config, semantic_enabled=True)
    assert await search.module.semantic.index("library") == 2
    assert await search.module.semantic.index("library") == 0  # content-hash skip
    assert await search.module.semantic.index("vault") == 1
    body = (await client.post("/api/v1/search", json={"q": "film", "mode": "semantic"})).json()
    assert body["semantic"] == "ok"
    titles = {(i["title"], i["matched_by"]) for g in body["groups"] for i in g["items"]}
    assert ("Cinema night", "semantic") in titles
    assert all(t != "Movie secrets" for t, _ in titles)  # forbidden kind never hydrated
