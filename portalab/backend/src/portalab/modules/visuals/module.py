"""Visuals module facade (spec 028): the registry of visual packs, its workflow and its files."""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.visuals import event_types as _event_types  # noqa: F401 — declares event types
from portalab.modules.visuals.github import GitHub
from portalab.modules.visuals.service import VisualPacks

OWNER = "module:visuals"
REFRESH_EVERY = 10.0  # seconds: how often a process checks the registry's epoch on its own
log = logging.getLogger(__name__)


class VisualsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        root: Path,
        github: GitHub | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit_sink = audit
        self.capabilities = capabilities
        self.clock = clock
        self.packs = VisualPacks(
            database,
            root,
            capabilities,
            github=github,
            audit=self._audit,
            announce=self._announce,
            clock=clock,
        )
        self._refresher: asyncio.Task[None] | None = None

    async def _audit(self, actor: Principal | None, action: str, context: dict[str, Any]) -> None:
        """Every action on a visual pack in the audit log, sensitive (it runs in members' pages)."""
        async with self.database.unit_of_work() as uow:
            await self.audit_sink.record(
                uow.session,
                AuditRecord(
                    action=action,
                    actor=actor or Principal(channel="system"),
                    resource=ResourceRef("visual_pack", str(context.get("pack") or "inbox")),
                    decision="allow",
                    result="success",
                    context=context,
                    sensitive=True,
                ),
            )

    async def _announce(
        self, session: AsyncSession, action: str, context: dict[str, Any], actor: Principal | None
    ) -> None:
        await self.events.publish(
            session,
            "visuals.pack_changed",
            {"action": action, **{k: v for k, v in context.items() if isinstance(v, str | int | bool)}},
            occurred_at=utc_now(self.clock),
            actor=actor,
        )

    async def start(self) -> None:
        """Brings the proof of concept's registry in once, then keeps this process's view of the registry
        fresh (the members' interfaces are told through the live stream)."""
        with contextlib.suppress(Exception):
            await self.packs.import_poc_state(Principal(channel="system"))
        with contextlib.suppress(Exception):
            await self.packs.refresh(force=True)
        if self._refresher is None:
            self._refresher = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(REFRESH_EVERY)
            try:
                await self.packs.refresh()
            except Exception:
                log.debug("visual packs: refresh failed", exc_info=True)

    async def stop(self) -> None:
        if self._refresher is not None:
            self._refresher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresher
            self._refresher = None
