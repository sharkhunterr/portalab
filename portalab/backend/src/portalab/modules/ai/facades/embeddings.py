"""Optional ``EmbeddingProvider`` for 008 (T028): the OpenAI-compatible ``/embeddings`` endpoint of the
configured provider. Registered only when ``ai.embeddings.model`` and ``ai.embeddings.dimension`` are set;
semantic search stays off otherwise."""

from collections.abc import Callable, Sequence

import httpx

from portalab.capabilities.ai import ProviderError


class OpenAICompatibleEmbeddings:
    def __init__(
        self,
        endpoint: Callable[[], str],
        model_id: str,
        dimension: int,
        api_key: Callable[[], str | None],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_id = model_id
        self.dimension = dimension
        self.api_key = api_key
        self.transport = transport

    async def embed(self, texts: Sequence[str], language: str | None) -> Sequence[Sequence[float]]:
        headers = {}
        key = self.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=30, follow_redirects=False
            ) as client:
                response = await client.post(
                    f"{self.endpoint().rstrip('/')}/embeddings",
                    json={"model": self.model_id, "input": [t[:8000] for t in texts]},
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("unreachable") from exc
        if response.status_code >= 400:
            raise ProviderError(f"http_{response.status_code}")
        vectors = [list(map(float, item["embedding"])) for item in response.json().get("data", [])]
        if len(vectors) != len(texts) or any(len(v) != self.dimension for v in vectors):
            raise ProviderError("invalid_response")
        return vectors
