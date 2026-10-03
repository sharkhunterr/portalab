"""News events (ids/state only): ``news.article_published`` (dedup ``(article, publish_seq)``),
``news.article_archived|restored|deleted|featured``."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:news"


class ArticleEvent(BaseModel):
    article: str
    publish_seq: int
    category: str | None = None


def register_event_types(registry: EventTypeRegistry) -> None:
    for action in ("published", "archived", "restored", "deleted", "featured"):
        name = f"news.article_{action}"
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=ArticleEvent,
                    open_payload=False,
                    dedup_fields=("article", "publish_seq"),
                    retention_class="business",
                    visibility_class="community",
                    aggregatable=frozenset({"category"}),
                    automatable=action == "published",
                )
            )
