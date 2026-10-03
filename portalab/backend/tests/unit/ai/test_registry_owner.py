"""018 T036 (F20) — owner-tagged tool registry: names ``<domain>.<verb>``, JSON-Schema objects, plugin
namespacing, no hijacking of another owner's tool, ``unregister(owner)`` removes all of its tools."""

import pytest

from portalab.capabilities.ai import AIError, AITool, AIToolRegistry, ToolResult


async def handler(principal: object, params: object) -> ToolResult:
    return ToolResult()


def tool(name: str, owner: str, schema: dict[str, object] | None = None) -> AITool:
    return AITool(name, "d", schema or {"type": "object"}, "ai.use", "read", handler, owner=owner)


def test_owner_lifecycle() -> None:
    registry = AIToolRegistry()
    registry.register(tool("media.search", "module:media"))
    registry.register(tool("media.request", "module:media"))
    registry.register(tool("kavita.read", "plugin:kavita"))
    with pytest.raises(AIError, match="belongs to"):
        registry.register(tool("media.search", "plugin:media"))
    assert registry.unregister("module:media") == 2
    assert [t.name for t in registry.all()] == ["kavita.read"]
    assert registry.unregister("plugin:kavita") == 1 and registry.all() == []


@pytest.mark.parametrize(
    ("name", "owner", "schema", "message"),
    [
        ("search", "module:x", None, "domain"),
        ("Media.Search", "module:x", None, "domain"),
        ("x.y", "module:x", {"type": "array"}, "object"),
        ("other.read", "plugin:kavita", None, "namespaced"),
    ],
)
def test_validation(name: str, owner: str, schema: dict[str, object] | None, message: str) -> None:
    with pytest.raises(AIError, match=message):
        AIToolRegistry().register(tool(name, owner, schema))
