"""Change propagation (T014; R10): ``admin.config_changed`` touching ``i18n.*`` keys bumps the resolver's
locale epoch (every process consuming the event) and announces ``i18n.policy_changed`` — plus
``i18n.language_added|disabled`` when the enabled set changes. Payloads carry setting names only."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventType, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher

OWNER = "module:i18n"
CONSUMER = "i18n.policy_changes"


class PolicyChanged(BaseModel):
    settings: list[str]
    change_seq: str


class LanguageChange(BaseModel):
    language: str
    change_seq: str


class TranslationUpdated(BaseModel):
    namespace: str
    language: str
    catalog_version: str


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup in (
        ("i18n.policy_changed", PolicyChanged, ("change_seq",)),
        ("i18n.language_added", LanguageChange, ("language", "change_seq")),
        ("i18n.language_disabled", LanguageChange, ("language", "change_seq")),
        ("i18n.translation_updated", TranslationUpdated, ("namespace", "language", "catalog_version")),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    dedup_fields=dedup,
                    retention_class="technical",
                    visibility_class="restricted",
                    automatable=True,
                )
            )


def policy_consumer(
    database: Database,
    events: Callable[[], EventPublisher],
    on_change: Callable[[], Any],
    enabled_languages: Callable[[], Any],
) -> Consumer:
    known: dict[str, set[str]] = {}

    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        settings = sorted(str(k) for k in envelope.payload.get("keys", []) if str(k).startswith("i18n."))
        if not settings:
            return
        on_change()
        change = str(envelope.payload.get("change_id", envelope.event_id))
        if not await ctx.idempotent_effect(f"i18n.policy:{change}"):
            return
        async with database.unit_of_work() as uow:
            publisher = events()
            await publisher.publish(
                uow.session,
                "i18n.policy_changed",
                {"settings": settings, "change_seq": change},
                occurred_at=envelope.occurred_at,
                source="i18n",
            )
            if "i18n.enabledLanguages" in settings:
                current = set(await enabled_languages())
                previous = known.get("enabled", current)
                for language in sorted(current - previous):
                    await publisher.publish(
                        uow.session,
                        "i18n.language_added",
                        {"language": language, "change_seq": change},
                        occurred_at=envelope.occurred_at,
                        source="i18n",
                    )
                for language in sorted(previous - current):
                    await publisher.publish(
                        uow.session,
                        "i18n.language_disabled",
                        {"language": language, "change_seq": change},
                        occurred_at=envelope.occurred_at,
                        source="i18n",
                    )
                known["enabled"] = current

    return Consumer(CONSUMER, frozenset({"admin.config_changed"}), handle, OWNER, replay_safe=False)


def plugin_state_consumer(plugins: Any) -> Consumer:
    """``plugin.state_changed`` (023): a disabled or removed plugin's catalogs are withdrawn (F20)."""

    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        plugin_id = str(envelope.payload.get("plugin_id", ""))
        if plugin_id and envelope.payload.get("state") in (
            "disabled",
            "uninstalled",
            "error",
            "incompatible",
        ):
            plugins.unregister(f"plugin:{plugin_id}")

    return Consumer(
        "i18n.plugin_catalogs", frozenset({"plugin.state_changed"}), handle, OWNER, replay_safe=True
    )
