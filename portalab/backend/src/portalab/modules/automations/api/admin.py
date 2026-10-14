"""Automation API (T011, T016, T027, T029; Admin in v1): catalog, drafts and versions, publish (confirmation
when sensitive actions are attested), pause / resume / archive / re-enable, dry-run (no side effects),
manual run (confirmation), executions, approvals and templates."""

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable
from portalab.core.time import utc_now
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.validate import effective_sensitivity
from portalab.modules.automations.dryrun.service import dry_run
from portalab.modules.automations.models import Approval, Automation, AutomationVersion, Execution
from portalab.modules.automations.module import AutomationsModule
from portalab.modules.automations.permissions import APPROVE, MANAGE, READ
from portalab.modules.automations.templates.loader import checked, load
from portalab.modules.automations.triggers.consumer import Live

router = APIRouter(prefix="/api/v1", tags=["automations"])


def automations_module(request: Request) -> AutomationsModule:
    module = getattr(request.app.state, "automations_module", None)
    if not isinstance(module, AutomationsModule):
        raise Unavailable("Automations are not available.", code="automations.unavailable")
    return module


Module = Annotated[AutomationsModule, Depends(automations_module)]
Reader = Annotated[Principal, require(READ)]
Manager = Annotated[Principal, require(MANAGE)]
Approver = Annotated[Principal, require(APPROVE)]


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class AutomationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=2, max_length=64)
    definition: dict[str, Any]


class AutomationUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str | None = None


class DryRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    actor_user_id: UUID | None = None
    subject_type: str | None = Field(default=None, max_length=64)
    subject_id: str | None = Field(default=None, max_length=200)


class InstantiateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=2, max_length=64)


class AutomationOut(BaseModel):
    id: UUID
    key: str
    name: str
    state: str
    current_version: int
    published_version: int | None
    identity_kind: str
    needs_review: bool
    suspend_reason: str | None
    consecutive_failures: int
    updated_at: datetime


class AutomationSummaryOut(AutomationOut):
    """027: a row of the automations page — when it runs, how it last went, how often lately."""

    trigger: dict[str, Any] | None = None
    steps: list[str] = Field(default_factory=list)
    last_status: str | None = None
    last_run_at: datetime | None = None
    runs_7d: int = 0
    failures_7d: int = 0


class AutomationDetailOut(AutomationOut):
    definition: dict[str, Any]
    versions: list[dict[str, Any]]


class AutomationExecutionOut(BaseModel):
    id: UUID
    automation_id: UUID
    version: int
    status: str
    trigger_ref: dict[str, Any]
    chain_id: str
    depth: int
    conditions_trace: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    batch_count: int
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None


class AutomationApprovalOut(BaseModel):
    id: UUID
    execution_id: UUID
    step_id: str
    action: str
    summary: str
    status: str
    created_at: datetime
    expires_at: datetime


def out(row: Automation) -> AutomationOut:
    return AutomationOut(
        id=row.id,
        key=row.key,
        name=row.name,
        state=row.state,
        current_version=row.current_version,
        published_version=row.published_version,
        identity_kind=row.identity_kind,
        needs_review=row.needs_review,
        suspend_reason=row.suspend_reason,
        consecutive_failures=row.consecutive_failures,
        updated_at=row.updated_at,
    )


def execution_out(row: Execution) -> AutomationExecutionOut:
    return AutomationExecutionOut(
        id=row.id,
        automation_id=row.automation_id,
        version=row.version,
        status=row.status,
        trigger_ref=row.trigger_ref,
        chain_id=row.chain_id,
        depth=row.depth,
        conditions_trace=row.conditions_trace,
        steps=row.steps,
        batch_count=row.batch_count,
        error_code=row.error_code,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def approval_out(row: Approval) -> AutomationApprovalOut:
    return AutomationApprovalOut(
        id=row.id,
        execution_id=row.execution_id,
        step_id=row.step_id,
        action=row.action,
        summary=row.summary,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


async def confirm(
    module: AutomationsModule, principal: Principal, action: str, target: UUID, token: str | None
) -> None:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource, payload = ResourceRef("automation", str(target)), {"action": action}
    if token is None:
        issued = await confirmations.issue(principal, MANAGE, resource, payload)
        raise ConfirmationRequired("Confirm this automation change.", extensions={"confirmation": issued})
    if not await confirmations.consume(token, principal, MANAGE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")


# --- catalog and templates (static paths first) -------------------------------------------------------
@router.get("/admin/automations/catalog")
async def catalog(_: Reader, module: Module) -> dict[str, Any]:
    return {
        "triggers": {
            "events": sorted(t.name for t in module.event_types.all() if t.automatable),
            "schedules": ["at", "relative", "recurring"],
            # 027: what each event carries (filters and ${event.<field>} variables) and what it means
            "event_fields": {
                t.name: sorted(t.schema.model_fields) if t.schema is not None else []
                for t in module.event_types.all()
                if t.automatable
            },
            "event_descriptions": {
                t.name: t.description for t in module.event_types.all() if t.automatable and t.description
            },
            # issue 122: the service data ``service.signal_changed`` tells about
            "signals": [
                {"key": s.key, "label": s.label, "description": s.description, "kind": s.kind}
                for s in module.signals.registry.all()
            ],
        },
        "conditions": [
            {"key": leaf.key, "description": leaf.description, "params": dict(leaf.params_schema)}
            for leaf in module.conditions.all()
        ],
        "actions": [
            {
                "key": a.key,
                "description": a.description,
                "permission": a.permission,
                "params": dict(a.params_schema),
                "required": list(a.required_params()),
                "sensitivity": effective_sensitivity(a, module.permissions),
                "ai_output_allowed": a.ai_output_allowed,
                "owner": a.owner,
            }
            for a in module.actions.all()
        ],
    }


@router.get("/admin/automations/signals")
async def signals(_: Reader, module: Module) -> list[dict[str, Any]]:
    """Issue 122: every service signal as it stands now, per service — what an automation can react to."""
    return await module.signals.current()


@router.get("/admin/automations/templates")
async def templates(_: Manager, module: Module) -> list[dict[str, Any]]:
    return [
        {
            "key": t.key,
            "title": t.title,
            "description": t.description,
            "valid": t.valid,
            "errors": t.errors,
            "definition": t.definition,
        }
        for t in checked(load(), module.definitions.validate)
    ]


@router.post(
    "/admin/automations/templates/{template_key}/instantiate", response_model=AutomationOut, status_code=201
)
async def instantiate(
    principal: Manager, template_key: str, body: InstantiateIn, module: Module
) -> AutomationOut:
    template = next((t for t in load() if t.key == template_key), None)
    if template is None:
        raise NotFound("This template does not exist.", code="automation.template_not_found")
    return out(await module.definitions.create(principal, body.key, template.definition))


@router.get("/admin/automations/approvals", response_model=list[AutomationApprovalOut])
async def approvals(
    _: Approver, module: Module, status: Literal["pending", "approved", "rejected", "expired"] = "pending"
) -> list[AutomationApprovalOut]:
    return [approval_out(a) for a in await module.approvals.queue(status)]


@router.post("/admin/automations/approvals/{approval_id}/approve")
async def approve(principal: Approver, approval_id: UUID, module: Module) -> dict[str, Any]:
    outcome = await module.approvals.approve(principal, approval_id)
    return {"status": outcome.status, "error": outcome.error}


@router.post("/admin/automations/approvals/{approval_id}/reject", status_code=204)
async def reject(principal: Approver, approval_id: UUID, module: Module) -> None:
    await module.approvals.reject(principal, approval_id)


@router.get("/admin/automations/executions/{execution_id}", response_model=AutomationExecutionOut)
async def execution(_: Reader, execution_id: UUID, module: Module) -> AutomationExecutionOut:
    row = await module.history.get(execution_id)
    if row is None:
        raise NotFound("This execution does not exist.", code="automation.execution_not_found")
    return execution_out(row)


@router.get("/admin/automations/executions", response_model=list[AutomationExecutionOut])
async def recent_executions(
    _: Reader,
    module: Module,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AutomationExecutionOut]:
    """027: the latest runs of every automation (the run history page), newest first."""
    async with module.database.session() as session:
        query = select(Execution).order_by(Execution.started_at.desc()).limit(limit)
        if status:
            query = query.where(Execution.status == status)
        rows = (await session.execute(query)).scalars().all()
    return [execution_out(r) for r in rows]


# --- automations -----------------------------------------------------------------------------------------
@router.get("/admin/automations", response_model=list[AutomationSummaryOut])
async def list_automations(_: Reader, module: Module) -> list[AutomationSummaryOut]:
    """027: with each one's trigger and steps, its last run and the runs of the last 7 days."""
    rows = await module.definitions.all()
    since = utc_now(module.clock) - timedelta(days=7)
    async with module.database.session() as session:
        versions = {
            (v.automation_id, v.version): v.definition
            for v in (await session.execute(select(AutomationVersion))).scalars()
        }
        last: dict[UUID, tuple[str, datetime]] = {}
        for automation_id, status, started in (
            await session.execute(
                select(Execution.automation_id, Execution.status, Execution.started_at)
                .distinct(Execution.automation_id)
                .order_by(Execution.automation_id, Execution.started_at.desc())
            )
        ).all():
            last[automation_id] = (status, started)
        counts: dict[UUID, tuple[int, int]] = {
            automation_id: (int(total), int(failed or 0))
            for automation_id, total, failed in (
                await session.execute(
                    select(
                        Execution.automation_id,
                        func.count(),
                        func.count().filter(Execution.status.in_(("failed", "timeout", "refused"))),
                    )
                    .where(Execution.started_at >= since)
                    .group_by(Execution.automation_id)
                )
            ).all()
        }
    items = []
    for row in rows:
        definition = versions.get((row.id, row.current_version)) or {}
        status, at = last.get(row.id, (None, None))
        runs, failed = counts.get(row.id, (0, 0))
        items.append(
            AutomationSummaryOut(
                **out(row).model_dump(),
                trigger=definition.get("trigger"),
                steps=[str(s.get("action", "")) for s in definition.get("steps", [])],
                last_status=status,
                last_run_at=at,
                runs_7d=runs,
                failures_7d=failed,
            )
        )
    return items


@router.post("/admin/automations", response_model=AutomationOut, status_code=201)
async def create(principal: Manager, body: AutomationIn, module: Module) -> AutomationOut:
    return out(await module.definitions.create(principal, body.key, body.definition))


@router.get("/admin/automations/{automation_id}", response_model=AutomationDetailOut)
async def detail(_: Reader, automation_id: UUID, module: Module) -> AutomationDetailOut:
    automation, versions = await module.definitions.get(automation_id)
    current = next(v for v in versions if v.version == automation.current_version)
    return AutomationDetailOut(
        **out(automation).model_dump(),
        definition=current.definition,
        versions=[
            {
                "version": v.version,
                "published_at": v.published_at.isoformat(),
                "standing_approvals": v.standing_approvals,
            }
            for v in versions
        ],
    )


@router.put("/admin/automations/{automation_id}", response_model=AutomationOut)
async def update(
    principal: Manager, automation_id: UUID, body: AutomationUpdateIn, module: Module
) -> AutomationOut:
    return out(await module.definitions.update(principal, automation_id, body.definition))


@router.post("/admin/automations/{automation_id}/publish", response_model=AutomationOut)
async def publish(principal: Manager, automation_id: UUID, body: ConfirmIn, module: Module) -> AutomationOut:
    automation, versions = await module.definitions.get(automation_id)
    current = next(v for v in versions if v.version == automation.current_version)
    if module.definitions.sensitive_actions(Definition.model_validate(current.definition)):
        await confirm(module, principal, "publish", automation_id, body.confirmation)
    return out(await module.definitions.publish(principal, automation_id))


@router.post("/admin/automations/{automation_id}/dry-run")
async def dry(principal: Manager, automation_id: UUID, body: DryRunIn, module: Module) -> dict[str, Any]:
    automation, versions = await module.definitions.get(automation_id)
    current = next(v for v in versions if v.version == automation.current_version)
    return await dry_run(
        automation,
        Definition.model_validate(current.definition),
        body.model_dump(),
        at=utc_now(module.clock),
        evaluator=module.evaluator,
        guard=module.guard,
        actions=module.actions,
        permissions=module.permissions,
        types=module.event_types,
        standing=current.standing_approvals,
    )


@router.post("/admin/automations/{automation_id}/run")
async def run(principal: Manager, automation_id: UUID, body: ConfirmIn, module: Module) -> dict[str, Any]:
    await confirm(module, principal, "run", automation_id, body.confirmation)
    automation, versions = await module.definitions.get(automation_id)
    if automation.published_version is None:
        raise Conflict("Publish the automation first.", code="automation.not_published")
    published = next(v for v in versions if v.version == automation.published_version)
    live = Live(
        automation.id, automation.key, published.version, Definition.model_validate(published.definition)
    )
    status = await module.triggers.fire(
        live, None, ref={"type": "manual", "by": str(principal.acting_for or principal.user_id)}
    )
    return {"status": status}


@router.get("/admin/automations/{automation_id}/executions", response_model=list[AutomationExecutionOut])
async def executions(
    _: Reader, automation_id: UUID, module: Module, status: str | None = None, before: datetime | None = None
) -> list[AutomationExecutionOut]:
    return [execution_out(e) for e in await module.history.list(automation_id, status=status, before=before)]


# generic transition route last: it must not shadow /dry-run, /run, /executions
@router.post("/admin/automations/{automation_id}/{transition}", response_model=AutomationOut)
async def transition(
    principal: Manager,
    automation_id: UUID,
    transition: Literal["pause", "resume", "archive", "reenable"],
    module: Module,
) -> AutomationOut:
    return out(await module.definitions.transition(principal, automation_id, transition))
