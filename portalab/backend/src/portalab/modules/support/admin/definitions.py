"""Support definitions (T018, T026, T030): ticket types, workflows and feedback forms. Workflows are
append-only versions (tickets pin theirs); types and forms carry a version bumped on every change; every
admin change is validated (closed schemas) and audited. The baseline (workflow ``baseline``, types
``bug|access_request|service_issue|question|other``, forms ``general|bug_report|feature_request``) is
seeded idempotently at start-up."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.support.models import FeedbackForm, TicketType, Workflow
from portalab.modules.support.workflow.engine import BASELINE, WorkflowDef, parse
from portalab.modules.support.workflow.types import BASELINE_FORMS, BASELINE_TYPES, FieldDef, parse_fields

BASELINE_KEY = "baseline"


class DefinitionNotFound(NotFound):
    default_code = "support.definition_not_found"
    default_title = "Definition not found"


class Definitions:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock
        self._seeded = False

    async def _seed(self) -> None:
        """The baseline exists before first use in every process (worker start-up also seeds it)."""
        if not self._seeded:
            await self.ensure_baseline()

    async def ensure_baseline(self) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await session.execute(
                insert(Workflow)
                .values(key=BASELINE_KEY, version=1, definition=BASELINE, created_at=now)
                .on_conflict_do_nothing()
            )
            for item in BASELINE_TYPES:
                await session.execute(
                    insert(TicketType)
                    .values(
                        key=item["key"],
                        label=item["label"],
                        workflow_key=BASELINE_KEY,
                        fields=item["fields"],
                        enabled=True,
                        version=1,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing()
                )
            for item in BASELINE_FORMS:
                await session.execute(
                    insert(FeedbackForm)
                    .values(
                        key=item["key"],
                        kind=item["kind"],
                        label=item["label"],
                        fields=item["fields"],
                        enabled=True,
                        version=1,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing()
                )
        self._seeded = True

    async def _audit(
        self, session: AsyncSession, actor: Principal, action: str, ref: str, context: dict[str, Any]
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("support_definition", ref),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )

    # --- workflows -------------------------------------------------------------------------------------
    async def workflow(self, key: str, version: int | None = None) -> tuple[int, WorkflowDef]:
        await self._seed()
        async with self.database.session() as session:
            if version is None:
                version = await session.scalar(select(func.max(Workflow.version)).where(Workflow.key == key))
            row = await session.get(Workflow, (key, version)) if version else None
        if row is None:
            raise DefinitionNotFound("This workflow does not exist.")
        return row.version, WorkflowDef.model_validate(row.definition)

    async def workflows(self) -> list[Workflow]:
        async with self.database.session() as session:
            latest = (
                select(Workflow.key, func.max(Workflow.version).label("v")).group_by(Workflow.key).subquery()
            )
            rows = await session.execute(
                select(Workflow).join(
                    latest, (Workflow.key == latest.c.key) & (Workflow.version == latest.c.v)
                )
            )
            return list(rows.scalars().all())

    async def save_workflow(self, actor: Principal, key: str, definition: Mapping[str, Any]) -> int:
        workflow = parse(definition)
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(select(func.max(Workflow.version)).where(Workflow.key == key))
            version = int(current or 0) + 1
            uow.session.add(
                Workflow(
                    key=key,
                    version=version,
                    definition=workflow.model_dump(by_alias=True),
                    created_at=utc_now(self.clock),
                )
            )
            await self._audit(uow.session, actor, "support.workflow_saved", key, {"version": version})
        return version

    # --- ticket types ----------------------------------------------------------------------------------
    async def types(self, *, enabled_only: bool = True) -> list[TicketType]:
        await self._seed()
        async with self.database.session() as session:
            stmt = select(TicketType).order_by(TicketType.key)
            if enabled_only:
                stmt = stmt.where(TicketType.enabled.is_(True))
            return list((await session.execute(stmt)).scalars().all())

    async def ticket_type(self, key: str) -> tuple[TicketType, list[FieldDef]]:
        await self._seed()
        async with self.database.session() as session:
            row = await session.get(TicketType, key)
        if row is None or not row.enabled:
            raise ValidationFailed("This ticket type does not exist.", code="ticket.unknown_type")
        return row, parse_fields(row.fields)

    async def save_type(
        self,
        actor: Principal,
        key: str,
        label: str,
        workflow_key: str,
        fields: Sequence[Mapping[str, Any]],
        enabled: bool,
        media: bool = False,
    ) -> TicketType:
        defs = parse_fields(fields)
        await self.workflow(workflow_key)  # must exist
        async with self.database.unit_of_work() as uow:
            if media:  # #354: one type takes the problems reported on a media
                await uow.session.execute(
                    update(TicketType)
                    .where(TicketType.key != key, TicketType.media.is_(True))
                    .values(media=False)
                )
            row = await uow.session.get(TicketType, key, with_for_update=True)
            payload = [d.model_dump() for d in defs]
            if row is None:
                row = TicketType(
                    key=key,
                    label=label,
                    workflow_key=workflow_key,
                    fields=payload,
                    enabled=enabled,
                    media=media,
                    version=1,
                    updated_at=utc_now(self.clock),
                )
                uow.session.add(row)
            else:
                row.label, row.workflow_key, row.fields, row.enabled = label, workflow_key, payload, enabled
                row.media = media
                row.version, row.updated_at = row.version + 1, utc_now(self.clock)
            await self._audit(uow.session, actor, "support.type_saved", key, {"version": row.version})
            return row

    # --- feedback forms --------------------------------------------------------------------------------
    async def forms(self, *, enabled_only: bool = True) -> list[FeedbackForm]:
        await self._seed()
        async with self.database.session() as session:
            stmt = select(FeedbackForm).order_by(FeedbackForm.key)
            if enabled_only:
                stmt = stmt.where(FeedbackForm.enabled.is_(True))
            return list((await session.execute(stmt)).scalars().all())

    async def form(self, key: str) -> tuple[FeedbackForm, list[FieldDef]]:
        await self._seed()
        async with self.database.session() as session:
            row = await session.get(FeedbackForm, key)
        if row is None or not row.enabled:
            raise ValidationFailed("This feedback form does not exist.", code="feedback.unknown_form")
        return row, parse_fields(row.fields)

    async def save_form(
        self,
        actor: Principal,
        key: str,
        kind: str,
        label: str,
        fields: Sequence[Mapping[str, Any]],
        enabled: bool,
        *,
        description: str = "",
        icon: str | None = None,
        requested: bool = False,
        opens_at: datetime | None = None,
        closes_at: datetime | None = None,
    ) -> FeedbackForm:
        defs = parse_fields(fields)
        if opens_at and closes_at and closes_at <= opens_at:
            raise ValidationFailed("A request closes after it opens.", code="feedback.request_window")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(FeedbackForm, key, with_for_update=True)
            payload = [d.model_dump() for d in defs]
            if row is None:
                row = FeedbackForm(
                    key=key,
                    kind=kind,
                    label=label,
                    fields=payload,
                    enabled=enabled,
                    version=1,
                    updated_at=utc_now(self.clock),
                )
                uow.session.add(row)
            else:
                row.kind, row.label, row.fields, row.enabled = kind, label, payload, enabled
                row.version, row.updated_at = row.version + 1, utc_now(self.clock)
            row.description, row.icon, row.requested = description, icon, requested
            row.opens_at, row.closes_at = opens_at, closes_at
            await self._audit(uow.session, actor, "support.form_saved", key, {"version": row.version})
            return row
