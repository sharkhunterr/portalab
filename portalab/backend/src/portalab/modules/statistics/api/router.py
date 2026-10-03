"""Statistics API (T013, T016, T017, T030, T031): consumption (catalog, one statistic, hidden sections,
Wrapped) and administration (definitions, activation, rebuild with confirmation, Wrapped, status)."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.statistics import StatResult, SubjectRef
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Unavailable, ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.statistics.models import RebuildRun, WrappedSnapshot
from portalab.modules.statistics.module import StatisticsModule
from portalab.modules.statistics.period.resolver import parse_period
from portalab.modules.statistics.permissions import SELF, STATISTICS_MANAGE, STATISTICS_READ
from portalab.modules.statistics.settings import HIDDEN_SECTIONS

router = APIRouter(prefix="/api/v1", tags=["statistics"])
REBUILD = "statistics.manage"


def statistics_module(request: Request) -> StatisticsModule:
    module = getattr(request.app.state, "statistics_module", None)
    if not isinstance(module, StatisticsModule):
        raise Unavailable("Statistics are not available.", code="statistics.unavailable")
    return module


Module = Annotated[StatisticsModule, Depends(statistics_module)]
Reader = Annotated[Principal, require(STATISTICS_READ)]
Self = Annotated[Principal, require(SELF)]
Manager = Annotated[Principal, require(STATISTICS_MANAGE)]


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class StatisticsCatalogEntryOut(BaseModel):
    key: str
    title_key: str
    description_key: str | None
    domain: str
    scope: str
    viz: str
    hideable: bool
    locked: bool
    unlock_hint: str | None
    period_options: list[str]
    hidden: bool


class StatisticsTrendOut(BaseModel):
    delta: float
    direction: Literal["up", "down", "flat"]
    previous_value: float
    percent: float | None


class StatResultOut(BaseModel):
    key: str
    state: Literal["available", "partial", "stale", "locked", "unavailable", "insufficient_data", "no_data"]
    definition_version: int | None
    as_of: str | None
    value: float | None
    series: list[dict[str, Any]]
    breakdown: list[dict[str, Any]]
    trend: StatisticsTrendOut | None
    unlock_hint: str | None
    source_states: dict[str, str]
    period_start: str | None
    period_end: str | None


class StatisticsPreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: list[str] = Field(default_factory=list, max_length=200)


class StatisticDefinitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]
    change_policy: Literal["forward_only", "rebuild"] = "forward_only"


class StatisticConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int | None = None
    reason: str = Field(default="", max_length=500)
    confirmation: str | None = Field(default=None, max_length=128)


class WrappedDefinitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,95}$")
    period_kind: Literal["month", "quarter", "year"]
    stat_keys: list[str] = Field(min_length=1, max_length=20)
    status: Literal["draft", "active", "retired"] = "active"


def _result(result: StatResult) -> StatResultOut:
    data = asdict(result)
    return StatResultOut(
        key=result.key,
        state=result.state,
        definition_version=result.definition_version,
        as_of=result.as_of.isoformat() if result.as_of else None,
        value=result.value,
        series=list(data["series"]),
        breakdown=list(data["breakdown"]),
        trend=StatisticsTrendOut(**data["trend"]) if result.trend else None,
        unlock_hint=result.unlock_hint,
        source_states=dict(result.source_states),
        period_start=result.period_start.isoformat() if result.period_start else None,
        period_end=result.period_end.isoformat() if result.period_end else None,
    )


async def _hidden(module: StatisticsModule, principal: Principal) -> list[str]:
    providers = module.capabilities.system_providers(CONFIG)
    user = principal.acting_for or principal.user_id
    if not providers or user is None:
        return []
    try:
        return list((await providers[0].provider.get(HIDDEN_SECTIONS, user_id=user)).value or [])
    except Exception:
        return []


@router.get("/statistics/catalog", response_model=list[StatisticsCatalogEntryOut])
async def catalog(principal: Reader, module: Module) -> list[StatisticsCatalogEntryOut]:
    hidden = set(await _hidden(module, principal))
    return [
        StatisticsCatalogEntryOut(
            **{**asdict(entry), "period_options": list(entry.period_options), "hidden": entry.key in hidden}
        )
        for entry in await module.provider.catalog(principal)
    ]


@router.get("/statistics/{key}", response_model=StatResultOut)
async def statistic(
    principal: Reader,
    key: str,
    module: Module,
    period: Annotated[
        Literal["day", "week", "month", "quarter", "year", "last_n_days", "custom"], Query()
    ] = "last_n_days",
    days: Annotated[int | None, Query(ge=1, le=3660)] = None,
    start: Annotated[str | None, Query(max_length=10)] = None,
    end: Annotated[str | None, Query(max_length=10)] = None,
    anchor: Annotated[str | None, Query(max_length=10)] = None,
    subject: Annotated[UUID | None, Query()] = None,
    filter: Annotated[list[str], Query(max_length=10)] = [],  # noqa: B006 — "dimension:value"
) -> StatResultOut:
    filters: dict[str, str] = {}
    for item in filter:
        name, _, value = item.partition(":")
        if not name or not value:
            raise ValidationFailed("Filters look like dimension:value.", code="statistics.invalid_filter")
        filters[name] = value
    result = await module.provider.get(
        key,
        viewer=principal,
        subject=SubjectRef("user", subject) if subject else None,
        period=parse_period(period, days=days, start=start, end=end, anchor=anchor),
        filters=filters,
    )
    return _result(result)


@router.get("/me/statistics/preferences")
async def get_preferences(principal: Self, module: Module) -> dict[str, list[str]]:
    return {"hidden": await _hidden(module, principal)}


@router.put("/me/statistics/preferences")
async def put_preferences(
    principal: Self, body: StatisticsPreferencesIn, module: Module
) -> dict[str, list[str]]:
    hideable = {entry.key for entry in await module.provider.catalog(principal) if entry.hideable}
    refused = sorted(set(body.hidden) - hideable)
    if refused:
        raise ValidationFailed(
            "These statistics cannot be hidden.",
            code="statistics.not_hideable",
            extensions={"statistics": refused},
        )
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Preferences are not available.", code="admin.unavailable")
    await providers[0].provider.set_user(principal, HIDDEN_SECTIONS, sorted(set(body.hidden)))
    return {"hidden": sorted(set(body.hidden))}


def _snapshot(row: WrappedSnapshot) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "wrapped_key": row.wrapped_key,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "scope": row.subject_scope,
        "payload": row.payload,
        "generated_at": row.generated_at.isoformat(),
    }


@router.get("/me/wrapped")
async def my_wrapped(principal: Self, module: Module) -> list[dict[str, Any]]:
    assert principal.user_id is not None
    return [_snapshot(row) for row in await module.wrapped.mine(principal.user_id)]


@router.get("/me/wrapped/{snapshot_id}")
async def my_wrapped_one(principal: Self, snapshot_id: UUID, module: Module) -> dict[str, Any]:
    assert principal.user_id is not None
    return _snapshot(await module.wrapped.one(principal.user_id, snapshot_id))


@router.get("/wrapped/community/{period_start}")
async def community_wrapped(principal: Reader, period_start: date, module: Module) -> list[dict[str, Any]]:
    return [_snapshot(row) for row in await module.wrapped.community(period_start)]


# --- administration ----------------------------------------------------------------------------------
@router.get("/admin/statistics/definitions")
async def list_definitions(_: Manager, module: Module) -> list[dict[str, Any]]:
    return await module.definitions.listing()


@router.get("/admin/statistics/definitions/{key}")
async def definition_versions(_: Manager, key: str, module: Module) -> list[dict[str, Any]]:
    return [
        {
            "version": row.version,
            "definition": row.definition,
            "change_policy": row.change_policy,
            "source": row.source,
            "created_at": row.created_at.isoformat(),
        }
        for row in await module.definitions.versions(key)
    ]


@router.post("/admin/statistics/definitions", status_code=201)
async def create_definition(
    principal: Manager, body: StatisticDefinitionIn, module: Module
) -> dict[str, Any]:
    version = await module.definitions.save(principal, body.definition, change_policy=body.change_policy)
    return {"key": body.definition.get("key"), "version": version}


@router.put("/admin/statistics/definitions/{key}")
async def update_definition(
    principal: Manager, key: str, body: StatisticDefinitionIn, module: Module
) -> dict[str, Any]:
    if body.definition.get("key") != key:
        raise ValidationFailed("The definition key cannot change.", code="statistics.invalid_definition")
    version = await module.definitions.save(principal, body.definition, change_policy=body.change_policy)
    return {"key": key, "version": version}


async def _confirmed(
    module: StatisticsModule, principal: Principal, action: str, key: str, body: StatisticConfirmIn
) -> None:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("statistic", key)
    payload = {"action": action, "version": body.version}
    if body.confirmation is None:
        issued = await confirmations.issue(principal, REBUILD, resource, payload)
        raise ConfirmationRequired(
            "Confirm this change to the statistic.", extensions={"confirmation": issued}
        )
    if not await confirmations.consume(body.confirmation, principal, REBUILD, resource, payload):
        raise ValidationFailed("This confirmation is not valid.", code="authz.confirmation_invalid")


@router.post("/admin/statistics/definitions/{key}/activate")
async def activate(principal: Manager, key: str, body: StatisticConfirmIn, module: Module) -> dict[str, Any]:
    await _confirmed(module, principal, "activate", key, body)
    return {"key": key, "active_version": await module.activate(principal, key, body.version)}


@router.post("/admin/statistics/definitions/{key}/retire")
async def retire(principal: Manager, key: str, module: Module) -> dict[str, Any]:
    await module.definitions.retire(principal, key)
    await module.sync()
    return {"key": key, "status": "retired"}


@router.post("/admin/statistics/definitions/{key}/rebuild")
async def rebuild(principal: Manager, key: str, body: StatisticConfirmIn, module: Module) -> dict[str, Any]:
    await _confirmed(module, principal, "rebuild", key, body)
    active = await module.definitions.get_active(key)
    if active is None:
        raise ValidationFailed("Only an active statistic can be rebuilt.", code="statistics.unknown")
    version = await module.definitions.save(principal, active.definition, change_policy="rebuild", force=True)
    await module.activate(principal, key, version)
    async with module.database.unit_of_work() as uow:
        uow.session.add(
            RebuildRun(
                stat_key=key,
                def_version=version,
                requested_by=principal.user_id,
                status="started",
                reason=body.reason,
                started_at=utc_now(module.clock),
            )
        )
    return {"key": key, "version": version, "status": "started"}


@router.get("/admin/statistics/wrapped")
async def wrapped_definitions(_: Manager, module: Module) -> list[dict[str, Any]]:
    return [
        {
            "key": d.key,
            "period_kind": d.period_kind,
            "stat_keys": d.stat_keys,
            "status": d.status,
            "version": d.version,
        }
        for d in await module.wrapped.definitions()
    ]


@router.put("/admin/statistics/wrapped")
async def put_wrapped(_: Manager, body: WrappedDefinitionIn, module: Module) -> dict[str, str]:
    await module.wrapped.save_definition(body.key, body.period_kind, body.stat_keys, body.status)
    return {"key": body.key}


@router.post("/admin/statistics/wrapped/generate")
async def generate_wrapped(_: Manager, module: Module) -> dict[str, int]:
    return {"generated": await module.wrapped.generate()}


@router.get("/admin/statistics/status")
async def status(_: Manager, module: Module) -> dict[str, Any]:
    return await module.status()
