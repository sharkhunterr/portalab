"""018 T027 — facades for other specs: ``SearchAssistant`` (008) synthesizes over permitted references
only and names only those as sources; ``interpret`` returns validated suggestions; the diagnosis executor
(016) uses no tools, returns a labelled analysis and fails loudly; the optional embeddings adapter; the
facades are withdrawn when the assistant is unavailable."""

import json
from collections.abc import Sequence
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.ai import ProviderError
from portalab.capabilities.search import ASSISTANT, SearchItem
from portalab.capabilities.support import DIAGNOSIS, DiagnosisFacts
from portalab.core.authz_port import Principal
from portalab.modules.ai.errors import AiUnavailable
from portalab.modules.ai.facades.embeddings import OpenAICompatibleEmbeddings
from tests.integration.ai.conftest import AiHarness

pytestmark = pytest.mark.integration


class Provider:
    kind = "wiki"
    label_key = "wiki"
    required_permission = "wiki.read"

    def __init__(self) -> None:
        self.seen: list[Principal] = []

    def facets(self) -> Sequence[object]:
        return ()

    async def search(self, *args: object, **kwargs: object) -> object:  # pragma: no cover - not used
        raise NotImplementedError

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        self.seen.append(principal)
        return [SearchItem("wiki", i, f"Page {i}", f"/wiki/{i}") for i in ids if i != "hidden"]


async def test_search_assistant(ai: AiHarness, people: dict[str, UUID]) -> None:
    provider = Provider()
    ai.search.register(provider, owner="module:wiki")  # type: ignore[arg-type]
    facade = ai.full.identity.capabilities.system_providers(ASSISTANT)[0].provider
    ai.provider.turns = [["Page a explains it [1], page b too [2], and [3]."]]
    events = [
        e
        async for e in facade.stream(
            "how to?", ai.p("ursula"), [("wiki", "a"), ("wiki", "b"), ("wiki", "hidden")]
        )
    ]
    refs = [e.data for e in events if e.type == "source_ref"]
    assert [(r["kind"], r["id"]) for r in refs] == [("wiki", "a"), ("wiki", "b")]
    assert "".join(e.data["text"] for e in events if e.type == "synthesis").startswith("Page a explains")
    assert provider.seen[0].channel == "ai" and provider.seen[0].acting_for == people["ursula"]
    assert {t.name for t in ai.provider.calls[0][1]} <= {"wiki__search", "services__status"}
    ai.provider.turns = [
        ['[{"label": "Open services", "route": "/services"}, {"label": "Bad", "route": "//evil"}]']
    ]
    suggestions = await facade.interpret("go to services", ai.p("ursula"), "/")
    assert [(s.label, s.route) for s in suggestions] == [("Open services", "/services"), ("Bad", None)]
    ai.provider.fail = "unreachable"
    assert await facade.interpret("x", ai.p("ursula"), None) == []
    assert [e.type for e in [e async for e in facade.stream("q", ai.p("ursula"), [])]] == ["error"]


async def test_diagnosis_executor(ai: AiHarness, people: dict[str, UUID]) -> None:
    executor = ai.full.identity.capabilities.system_providers(DIAGNOSIS)[0].provider
    facts = DiagnosisFacts("Media won't play", {"service_id": "s1", "state": "unavailable"}, (), ())
    ai.provider.turns = [
        [
            json.dumps(
                {
                    "summary": "Media is down.",
                    "proposed_solution": "Wait for the fix.",
                    "solved": False,
                    "suggested_title": "Media playback fails",
                    "suggested_type": "service_issue",
                }
            )
        ]
    ]
    analysis = await executor.analyze(facts, ai.p("ursula"))
    assert (
        analysis.summary == "Media is down."
        and analysis.suggested_type == "service_issue"
        and not analysis.solved
    )
    assert ai.provider.calls[0][1] == []  # no tools: the diagnosis never acts
    assert "untrusted-data" in ai.provider.calls[0][0][1].content
    ai.provider.fail = "timeout"
    with pytest.raises(AiUnavailable):
        await executor.analyze(facts, ai.p("ursula"))


async def test_facades_follow_availability(ai: AiHarness) -> None:
    capabilities = ai.full.identity.capabilities
    assert capabilities.system_providers(DIAGNOSIS)
    ai.module.config = type(ai.module.config)(enabled=False)
    ai.module.sync_facades()
    assert not capabilities.system_providers(DIAGNOSIS) and not capabilities.system_providers(ASSISTANT)
    ai.module.config = type(ai.module.config)(enabled=True)
    ai.module.sync_facades()
    assert capabilities.system_providers(DIAGNOSIS)


async def test_embeddings_adapter() -> None:
    def server(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]} for _ in texts]})

    embeddings = OpenAICompatibleEmbeddings(
        lambda: "http://llm.test/v1", "embed", 3, lambda: "k", transport=httpx.MockTransport(server)
    )
    assert await embeddings.embed(["a", "b"], None) == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    wrong = OpenAICompatibleEmbeddings(
        lambda: "http://llm.test/v1", "embed", 4, lambda: None, transport=httpx.MockTransport(server)
    )
    with pytest.raises(ProviderError):
        await wrong.embed(["a"], None)
