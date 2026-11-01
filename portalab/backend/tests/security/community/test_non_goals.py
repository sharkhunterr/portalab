"""012 T004 — non-goal guard (CI): the OpenAPI paths and the ``community`` schema carry no friends,
followers, social graph, direct messages, likes, reactions or chat artifacts. Chat is a plugin-only
extension point (see ``docs/community.md``); this test fails the build on any match."""

import re

import pytest
from sqlalchemy import text

from portalab.core.db import Database

FORBIDDEN = re.compile(
    r"^(friends?|followers?|following|follows?|graph|messages?|dms?|likes?|reactions?|chats?)$"
)

# The 018 assistant's conversation messages are a user talking to the AI, not user-to-user messaging.
ASSISTANT = "/api/v1/ai/"
# #299: « Mon fil » follows works, people of their credits and genres — privately, a member to a subject
# of the library, never a member to another member.
MEDIA_FOLLOWS = "/api/v1/me/media/follows"


def tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", name.lower()) if t}


def offending(names: list[str]) -> list[str]:
    return [n for n in names if any(FORBIDDEN.match(t) for t in tokens(n))]


def test_openapi_paths_have_no_social_graph() -> None:
    from portalab.app.main import create_app

    schema = create_app(static_dir=None).openapi()
    community = [p for p in schema["paths"] if "/community" in p]
    assert community, "the community routes must be mounted"
    assert offending([p for p in schema["paths"] if not p.startswith((ASSISTANT, MEDIA_FOLLOWS))]) == []
    components = list(schema.get("components", {}).get("schemas", {}))
    assert offending([c for c in components if c.lower().startswith("community")]) == []


@pytest.mark.integration
async def test_schema_has_no_social_graph(database: Database) -> None:
    async with database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'community'"
                )
            )
        ).all()
    assert rows, "the community schema must exist"
    names = sorted({r.table_name for r in rows} | {f"{r.table_name}.{r.column_name}" for r in rows})
    assert offending(names) == []


def test_guard_catches_violations() -> None:
    assert offending(["/api/v1/community/friends", "community.follow_edges", "direct_message"]) == [
        "/api/v1/community/friends",
        "community.follow_edges",
        "direct_message",
    ]
    assert offending(["/api/v1/admin/x", "community.feed_entries.text_key"]) == []
