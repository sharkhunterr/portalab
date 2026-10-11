"""UI events (T030; FR-024): ``theme.changed``, ``theme.policy_changed`` and
``accessibility.preference_changed``, derived from Administration's ``admin.config_changed`` (which carries
the changed setting names only — never values) by a replay-safe consumer. Dedup ``(user, setting,
change_seq)`` where ``change_seq`` is the configuration change id."""

from collections.abc import Callable

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventType, EventTypeRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef

OWNER = "module:ui"
CONSUMER = "ui.preference_events"
POLICY_KEYS = {
    "ui.allowedThemes",
    "ui.defaultTheme",
    "ui.textScale.min",
    "ui.textScale.max",
    "ui.forceReducedMotion",
}
ACCESSIBILITY_KEYS = {
    "ui.textScale",
    "ui.contrast",
    "ui.reducedMotion",
    "ui.animations",
    "ui.soundEnabled",
    "ui.density",
    "ui.notificationPosition",
    "ui.notificationDurationSeconds",
    "ui.notificationStyle",
    "ui.notificationAnimation",
    "ui.palette",
}


class SettingChange(BaseModel):
    setting: str
    change_seq: str


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in ("theme.changed", "theme.policy_changed", "accessibility.preference_changed"):
        registry.register(
            EventType(
                name=name,
                owner=OWNER,
                schema=SettingChange,
                open_payload=False,
                dedup_fields=("setting", "change_seq"),
                retention_class="technical",
                visibility_class="private",
            )
        )


def event_for(setting: str) -> str | None:
    if setting == "ui.theme":
        return "theme.changed"
    if setting in POLICY_KEYS:
        return "theme.policy_changed"
    if setting in ACCESSIBILITY_KEYS:
        return "accessibility.preference_changed"
    return None


def preference_consumer(database: Database, publisher: Callable[[], EventPublisher]) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        settings = [str(k) for k in envelope.payload.get("keys", []) if str(k).startswith("ui.")]
        change_seq = str(envelope.payload.get("change_id", envelope.event_id))
        if not settings:
            return
        async with database.unit_of_work() as uow:
            for setting in settings:
                name = event_for(setting)
                if name is None or not await ctx.idempotent_effect(f"{name}:{setting}:{change_seq}"):
                    continue
                await _publish(uow.session, publisher(), name, setting, change_seq, envelope)

    return Consumer(CONSUMER, frozenset({"admin.config_changed"}), handle, OWNER, replay_safe=False)


async def _publish(
    session: AsyncSession,
    events: EventPublisher,
    name: str,
    setting: str,
    change_seq: str,
    envelope: Envelope,
) -> None:
    user = envelope.actor_user_id
    await events.publish(
        session,
        name,
        {"setting": setting, "change_seq": change_seq},
        occurred_at=envelope.occurred_at,
        actor=Principal(user_id=user) if user else Principal(channel="system"),
        subject=SubjectRef("user", str(user)) if user and name != "theme.policy_changed" else None,
        source="ui",
    )
