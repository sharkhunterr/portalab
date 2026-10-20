"""``ollama`` connector (issue 169): an Ollama server on the local network — the assistant's models.

* ``ai.models``: the models it holds (``GET /api/tags``: family, size, quantization, what each can do —
  completion, tools, embedding) and those loaded in memory (``GET /api/ps``: the graphics memory they take);
  its OpenAI-compatible address (``<address>/v1``), the one the assistant is pointed at.
* ``service.health_probe``: ``GET /api/version``.

Ollama has no authentication of its own (it sits on the local network, or behind a proxy): the connector
only needs its address.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from portalab.capabilities.ai import MODELS, MODELS_SPEC, ModelInfo
from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, binding

MAX_MODELS = 500
EMBEDDING_FAMILIES = frozenset({"bert", "nomic-bert"})


def _size(value: Any) -> int | None:
    return (
        int(value) if isinstance(value, int | float) and not isinstance(value, bool) and value > 0 else None
    )


def _text(value: Any, limit: int = 64) -> str | None:
    return str(value)[:limit] if isinstance(value, str) and value else None


def map_model(row: Mapping[str, Any], loaded: Mapping[str, Mapping[str, Any]]) -> ModelInfo | None:
    """One model of ``/api/tags``, with its place in memory from ``/api/ps``; ``None`` without a name."""
    name = _text(row.get("name") or row.get("model"), 200)
    if name is None:
        return None
    raw = row.get("details")
    details: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    families = {str(f) for f in details.get("families") or [] if isinstance(f, str)}
    family = _text(details.get("family"))
    abilities = {str(c) for c in row.get("capabilities") or [] if isinstance(c, str)}
    embedding = (
        "embedding" in abilities or bool(({family} | families) & EMBEDDING_FAMILIES) or "embed" in name
    )
    running = loaded.get(name)
    return ModelInfo(
        name=name,
        family=family,
        parameters=_text(details.get("parameter_size"), 16),
        quantization=_text(details.get("quantization_level"), 16),
        size_bytes=_size(row.get("size")),
        loaded=running is not None,
        vram_bytes=_size(running.get("size_vram")) if running is not None else None,
        embedding=embedding,
        tools=("tools" in abilities) if abilities else None,
    )


class OllamaConnector(HttpConnector):
    key = "ollama"
    name = "Ollama"
    description = "Language models on your own network — the assistant's brain: its models, those in memory."
    icon = "brain"
    category = "ai"
    secret_fields: frozenset[str] = frozenset()
    provides: Sequence[CapabilityBinding] = (CapabilityBinding(MODELS_SPEC), binding(HEALTH_PROBE))
    status_path = "/api/version"
    public_path = "/api/version"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or not isinstance(status.get("version"), str):
            raise InvalidPayload("not an Ollama version")
        return f"Ollama {status['version']}"

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and isinstance(public.get("version"), str)

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == MODELS:
            return OllamaModels(self, service)
        return super().provider(capability, service)


class OllamaModels:
    def __init__(self, connector: OllamaConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    def endpoint(self) -> str:
        return f"{str(self.service.config.get('base_url') or '').rstrip('/')}/v1"

    async def models(self) -> Sequence[ModelInfo]:
        tags = await self.connector.get_json(self.service, "/api/tags")
        if not isinstance(tags, Mapping) or not isinstance(tags.get("models"), list):
            raise InvalidPayload("unexpected /api/tags payload")
        try:
            running = await self.connector.get_json(self.service, "/api/ps")
        except (ConnectionError, OSError, InvalidPayload):
            running = {}  # what is loaded is a detail: the models still list
        loaded = {
            str(row.get("name")): row
            for row in (running.get("models") if isinstance(running, Mapping) else None) or []
            if isinstance(row, Mapping) and row.get("name")
        }
        found = [map_model(row, loaded) for row in tags["models"][:MAX_MODELS] if isinstance(row, Mapping)]
        return sorted((m for m in found if m is not None), key=lambda m: (m.embedding, m.name))
