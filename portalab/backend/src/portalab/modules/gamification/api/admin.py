"""Admin API (T011, T014, T022, T024, T026): reward rules (versioned: draft → publish → retire, simulate),
level curve, achievements, manual grants (confirmation above the threshold), ledger views (audited),
verification and anomaly review. ``gamification.manage`` / ``rewards.grant`` / ``economy.manage``."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable, ValidationFailed
from portalab.core.time import utc_now
from portalab.modules.gamification.api.me import EconomyTransactionPage, Module, transaction_out
from portalab.modules.gamification.models import RewardRule
from portalab.modules.gamification.permissions import ECONOMY_MANAGE, GRANT, MANAGE
from portalab.modules.gamification.rules.simulate import simulate
from portalab.modules.gamification.verify.verifier import verify

router = APIRouter(prefix="/api/v1", tags=["gamification-admin"])
Manager = Annotated[Principal, require(MANAGE)]
Granter = Annotated[Principal, require(GRANT)]
Economist = Annotated[Principal, require(ECONOMY_MANAGE)]
KEY = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class RewardRuleOut(BaseModel):
    key: str
    version: int
    status: str
    event_type: str
    definition: dict[str, Any]
    effective_from: datetime | None
    retired_at: datetime | None
    created_at: datetime


class RewardRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class RulePublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class RuleSimulateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any] | None = None  # a draft to try; default: the latest version of the rule
    samples: list[dict[str, Any]] = Field(max_length=50)


class LevelCurveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class AchievementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class ManualGrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    value: Literal["xp", "contribution", "coins"]
    amount: int = Field(ge=1, le=1_000_000)
    reason: str = Field(min_length=3, max_length=200)
    idempotency: str | None = Field(default=None, max_length=100)
    confirmation: str | None = None


class AnomalyDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=200)


def rule_out(row: RewardRule) -> RewardRuleOut:
    return RewardRuleOut(
        key=row.key,
        version=row.version,
        status=row.status,
        event_type=row.event_type,
        definition=row.definition,
        effective_from=row.effective_from,
        retired_at=row.retired_at,
        created_at=row.created_at,
    )


# --- rules ---------------------------------------------------------------------------------------------
@router.get("/admin/gamification/rules", response_model=list[RewardRuleOut])
async def list_rules(_: Manager, module: Module) -> list[RewardRuleOut]:
    return [rule_out(r) for r in await module.rules.latest()]


@router.get("/admin/gamification/rules/{key}", response_model=list[RewardRuleOut])
async def rule_versions(_: Manager, key: str, module: Module) -> list[RewardRuleOut]:
    return [rule_out(r) for r in await module.rules.versions(key)]


@router.post("/admin/gamification/rules/{key}", response_model=RewardRuleOut, status_code=201)
async def save_rule(principal: Manager, key: str, body: RewardRuleIn, module: Module) -> RewardRuleOut:
    if not re.fullmatch(KEY, key) or len(key) > 96:
        raise ValidationFailed("Invalid rule key.", code="economy.rule_invalid")
    return rule_out(await module.rules.save(principal, key, body.definition))


@router.post("/admin/gamification/rules/{key}/publish", response_model=RewardRuleOut)
async def publish_rule(principal: Manager, key: str, body: RulePublishIn, module: Module) -> RewardRuleOut:
    return rule_out(await module.rules.publish(principal, key, body.version))


@router.post("/admin/gamification/rules/{key}/simulate")
async def simulate_rule(
    principal: Manager, key: str, body: RuleSimulateIn, module: Module
) -> list[dict[str, Any]]:
    user = principal.acting_for or principal.user_id
    assert user is not None
    definition = body.definition if body.definition is not None else (await module.rules.get(key)).definition
    return await simulate(
        definition,
        body.samples,
        types=module.event_types,
        combiner=module.combiner,
        cap=module.config.max_total_boost,
        user=user,
        now=utc_now(module.clock),
    )


@router.post("/admin/gamification/rules/{key}/retire", response_model=RewardRuleOut)
async def retire_rule(principal: Manager, key: str, module: Module) -> RewardRuleOut:
    return rule_out(await module.rules.retire(principal, key))


# --- level curve and achievements --------------------------------------------------------------------
@router.get("/admin/gamification/level-curve")
async def get_curve(_: Manager, module: Module) -> dict[str, Any]:
    curve = await module.levels.curve()
    return {
        "version": curve.version,
        "definition": {"kind": "power", "base": curve.base, "exponent": curve.exponent},
        "preview": [{"level": n, "xp": curve.threshold(n)} for n in range(1, 11)],
    }


@router.put("/admin/gamification/level-curve")
async def put_curve(principal: Manager, body: LevelCurveIn, module: Module) -> dict[str, Any]:
    curve = await module.levels.publish(body.definition)
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action="economy.level_curve_published",
                actor=principal,
                resource=ResourceRef("level_curve", str(curve.version)),
                decision="allow",
                sensitive=True,
            ),
        )
    return await get_curve(principal, module)


@router.get("/admin/gamification/achievements")
async def list_achievements(_: Manager, module: Module) -> list[dict[str, Any]]:
    return [
        {
            "key": d.key,
            "version": d.version,
            "definition": d.definition.model_dump(),
            "source": d.source_ref or "own",
        }
        for d in await module.achievements.definitions(utc_now(module.clock))
    ]


@router.put("/admin/gamification/achievements/{key}")
async def save_achievement(
    principal: Manager, key: str, body: AchievementIn, module: Module
) -> dict[str, Any]:
    row = await module.achievements.save(principal, key, body.definition)
    return {"key": row.key, "version": row.version, "definition": row.definition}


@router.delete("/admin/gamification/achievements/{key}", status_code=204)
async def retire_achievement(principal: Manager, key: str, module: Module) -> Response:
    await module.achievements.retire(principal, key)
    return Response(status_code=204)


# --- manual grants -----------------------------------------------------------------------------------
@router.post(
    "/admin/gamification/manual-grants",
    responses={
        409: {"description": "authz.confirmation_required (carries `confirmation`) above the threshold"}
    },
)
async def manual_grant(principal: Granter, body: ManualGrantIn, module: Module) -> dict[str, Any]:
    idempotency = body.idempotency or str(uuid.uuid4())
    if body.amount >= module.config.manual_grant_confirm_threshold:
        providers = module.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are not available.", code="authz.unavailable")
        confirmations = providers[0].provider
        resource = ResourceRef("progression", str(body.user_id), owner_id=body.user_id)
        payload = {"value": body.value, "amount": body.amount, "user": str(body.user_id)}
        if body.confirmation is None:
            issued = await confirmations.issue(principal, GRANT, resource, payload)
            raise ConfirmationRequired(
                "This grant is above the confirmation threshold. Confirm to continue.",
                extensions={"confirmation": issued},
            )
        if not await confirmations.consume(body.confirmation, principal, GRANT, resource, payload):
            raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    transaction = await module.rewards.grant_manual(
        principal, body.user_id, body.value, body.amount, reason=body.reason, idempotency_key=idempotency
    )
    assert transaction is not None
    return {"transaction": transaction_out(transaction).model_dump(mode="json")}


# --- ledger, verification and anomalies (economy.manage) ---------------------------------------------
@router.get("/admin/economy/transactions", response_model=EconomyTransactionPage)
async def ledger(
    principal: Economist,
    module: Module,
    user: UUID,
    value: Literal["xp", "contribution", "coins"] | None = None,
    cursor: str | None = None,
) -> EconomyTransactionPage:
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action="economy.ledger_viewed",
                actor=principal,
                resource=ResourceRef("progression", str(user), owner_id=user),
                decision="allow",
                sensitive=True,
            ),
        )
    page = await module.economy.history(user, value=value, cursor=cursor)
    return EconomyTransactionPage(
        items=[transaction_out(t) for t in page.items], next_cursor=page.next_cursor
    )


@router.get("/admin/economy/verify")
async def verify_ledger(_: Economist, module: Module) -> dict[str, Any]:
    report = await verify(module.database)
    return {
        "ok": report.ok,
        "checked": report.checked,
        "drifts": [
            {"user_id": str(d.user_id), "value": d.value, "ledger": d.ledger, "balance": d.balance}
            for d in report.drifts
        ],
    }


@router.get("/admin/economy/anomalies")
async def anomalies(
    _: Economist, module: Module, status: Literal["open", "dismissed", "confirmed"] = "open"
) -> list[dict[str, Any]]:
    return [
        {
            "id": str(flag.id),
            "user_id": str(flag.user_id),
            "kind": flag.kind,
            "window_start": flag.window_start.isoformat(),
            "evidence": flag.evidence,
            "status": flag.status,
            "created_at": flag.created_at.isoformat(),
            "withheld": [
                {
                    "id": str(w.id),
                    "value": w.value,
                    "amount": w.proposed_delta,
                    "rule": w.rule_key,
                    "status": w.status,
                    "occurred_at": w.occurred_at.isoformat(),
                }
                for w in withheld
            ],
        }
        for flag, withheld in await module.anomalies.queue(status)
    ]


@router.post("/admin/economy/anomalies/{flag_id}/approve")
async def approve(
    principal: Economist, flag_id: UUID, body: AnomalyDecisionIn, module: Module
) -> dict[str, Any]:
    return {"transactions": [str(t) for t in await module.anomalies.approve(principal, flag_id, body.reason)]}


@router.post("/admin/economy/anomalies/{flag_id}/reject")
async def reject(
    principal: Economist, flag_id: UUID, body: AnomalyDecisionIn, module: Module
) -> dict[str, Any]:
    return {"dropped": await module.anomalies.reject(principal, flag_id, body.reason)}


@router.post("/admin/economy/anomalies/{flag_id}/confirm-abuse")
async def confirm_abuse(
    principal: Economist, flag_id: UUID, body: AnomalyDecisionIn, module: Module
) -> dict[str, Any]:
    return {
        "corrections": [str(t) for t in await module.anomalies.confirm_abuse(principal, flag_id, body.reason)]
    }
