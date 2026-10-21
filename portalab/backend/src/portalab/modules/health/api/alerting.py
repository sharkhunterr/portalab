"""Alerting rules (027): what an outage does, by service importance — an incident after a delay, closed
when the service is back, notifications and e-mails to members and administrators, whether it counts in
the portal's health. Each service may override any field (connectors ``alerting``)."""

from dataclasses import asdict, replace
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.health import DEFAULT_ALERT_RULES, MAX_ALERT_DELAY, alert_rules
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.health.api.common import Module
from portalab.modules.health.permissions import SERVICES_MANAGE
from portalab.modules.health.settings import SETTINGS

router = APIRouter(prefix="/api/v1", tags=["health"])


class AlertRuleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident: bool
    incident_after: int = Field(ge=1, le=MAX_ALERT_DELAY)
    auto_resolve: bool
    notify_after: int = Field(ge=0, le=MAX_ALERT_DELAY)
    notify_members: bool
    notify_admins: bool
    email_members: bool
    email_admins: bool
    degrades_portal: bool
    banner: bool = False


class AlertRulesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    critical: AlertRuleBody
    major: AlertRuleBody
    minor: AlertRuleBody
    internal: AlertRuleBody


class AlertRulesOut(BaseModel):
    rules: AlertRulesBody
    defaults: AlertRulesBody


def _out(module: Module) -> AlertRulesOut:
    current = {k: asdict(v) for k, v in alert_rules(module.config.alert_rules).items()}
    defaults = {k: asdict(v) for k, v in DEFAULT_ALERT_RULES.items()}
    return AlertRulesOut(
        rules=AlertRulesBody.model_validate(current), defaults=AlertRulesBody.model_validate(defaults)
    )


@router.get("/health/alert-rules", response_model=AlertRulesOut)
async def get_alert_rules(_: Annotated[Principal, require(SERVICES_MANAGE)], module: Module) -> AlertRulesOut:
    return _out(module)


@router.put("/health/alert-rules", response_model=AlertRulesOut)
async def put_alert_rules(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], body: AlertRulesBody, module: Module
) -> AlertRulesOut:
    providers = module.state.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Settings cannot be changed right now.", code="admin.unavailable")
    value = body.model_dump()
    await providers[0].provider.set_global(principal, SETTINGS["alert_rules"], value, reason="alert rules")
    module.config = replace(module.config, alert_rules=value)  # this process at once; others on refresh
    return _out(module)
