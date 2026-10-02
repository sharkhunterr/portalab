"""Navigation epochs (T014; R15, FR-030/032). Any change to rights (``permission.*``, 003), enablement
(``admin.module_toggled|plugin_toggled``, 020; ``plugin.state_changed``, 023) or the shell configuration
bumps an epoch in ``shell.epochs`` — shared by every process — and notifies subscribers on the live stream
(``navigation.changed``, payload: the new version only). Cached navigation views are keyed by these epochs."""

from collections.abc import Callable

from sqlalchemy import select, update

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.shell.models import Epoch

CONSUMER = "shell.navigation_epochs"
PERMISSION_EVENTS = frozenset(
    {
        "permission.role_assigned",
        "permission.role_revoked",
        "permission.group_changed",
        "permission.permission_granted",
        "permission.permission_revoked",
        "permission.policy_changed",
    }
)
MODULE_EVENTS = frozenset({"admin.module_toggled", "admin.plugin_toggled", "plugin.state_changed"})


class Epochs:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def current(self) -> tuple[int, int]:
        async with self.database.session() as session:
            rows: dict[str, int] = {
                name: int(value)
                for name, value in (await session.execute(select(Epoch.name, Epoch.value))).all()
            }
        return int(rows.get("permission", 0)), int(rows.get("module", 0))

    async def bump(self, name: str) -> int:
        async with self.database.unit_of_work() as uow:
            value = (
                await uow.session.execute(
                    update(Epoch)
                    .where(Epoch.name == name)
                    .values(value=Epoch.value + 1, updated_at=utc_now(self.clock))
                    .returning(Epoch.value)
                )
            ).scalar_one()
            await publish_live(
                uow.session,
                topic="navigation.changed",
                payload={"version": f"{name}:{value}"},
                clock=self.clock,
            )
            return int(value)


def epoch_for(event_type: str, payload_keys: list[str]) -> str | None:
    if event_type in PERMISSION_EVENTS:
        return "permission"
    if event_type in MODULE_EVENTS:
        return "module"
    if event_type == "admin.config_changed" and any(k.startswith("shell.") for k in payload_keys):
        return "module"
    return None


def epoch_consumer(epochs: Callable[[], Epochs]) -> Consumer:
    async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
        name = epoch_for(envelope.type, [str(k) for k in envelope.payload.get("keys", [])])
        if name is not None and await ctx.idempotent_effect(f"epoch:{envelope.event_id}"):
            await epochs().bump(name)

    return Consumer(
        CONSUMER,
        PERMISSION_EVENTS | MODULE_EVENTS | {"admin.config_changed"},
        handle,
        "module:shell",
        replay_safe=True,
    )
