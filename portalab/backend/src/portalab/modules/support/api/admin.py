"""Support configuration API (T026, T030): ticket types, workflows (versioned, validated) and feedback
forms — ``support.configure``, audited."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.support.api.incidents import support_module
from portalab.modules.support.module import SupportModule

router = APIRouter(prefix="/api/v1", tags=["support"])
Module = Annotated[SupportModule, Depends(support_module)]
Configurer = Annotated[Principal, require("support.configure")]


class SupportTypeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    workflow_key: str = Field(default="baseline", max_length=60)
    fields: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    enabled: bool = True


class SupportTypeOut(SupportTypeIn):
    key: str
    version: int
    updated_at: datetime


class SupportWorkflowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict[str, Any]


class SupportWorkflowOut(BaseModel):
    key: str
    version: int
    definition: dict[str, Any]


class SupportFormIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=30)
    label: str = Field(min_length=1, max_length=120)
    fields: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    enabled: bool = True


class SupportFormOut(SupportFormIn):
    key: str
    version: int


@router.get("/admin/support/types", response_model=list[SupportTypeOut])
async def list_types(principal: Configurer, module: Module) -> list[SupportTypeOut]:
    return [
        SupportTypeOut(
            key=t.key,
            label=t.label,
            workflow_key=t.workflow_key,
            fields=t.fields,
            enabled=t.enabled,
            version=t.version,
            updated_at=t.updated_at,
        )
        for t in await module.definitions.types(enabled_only=False)
    ]


@router.put("/admin/support/types/{key}", response_model=SupportTypeOut)
async def put_type(principal: Configurer, key: str, body: SupportTypeIn, module: Module) -> SupportTypeOut:
    t = await module.definitions.save_type(
        principal, key[:60], body.label, body.workflow_key, body.fields, body.enabled
    )
    return SupportTypeOut(
        key=t.key,
        label=t.label,
        workflow_key=t.workflow_key,
        fields=t.fields,
        enabled=t.enabled,
        version=t.version,
        updated_at=t.updated_at,
    )


@router.get("/admin/support/workflows", response_model=list[SupportWorkflowOut])
async def list_workflows(principal: Configurer, module: Module) -> list[SupportWorkflowOut]:
    return [
        SupportWorkflowOut(key=w.key, version=w.version, definition=w.definition)
        for w in await module.definitions.workflows()
    ]


@router.put("/admin/support/workflows/{key}", response_model=SupportWorkflowOut)
async def put_workflow(
    principal: Configurer, key: str, body: SupportWorkflowIn, module: Module
) -> SupportWorkflowOut:
    version = await module.definitions.save_workflow(principal, key[:60], body.definition)
    saved, workflow = await module.definitions.workflow(key[:60], version)
    return SupportWorkflowOut(key=key[:60], version=saved, definition=workflow.model_dump(by_alias=True))


@router.get("/admin/support/forms", response_model=list[SupportFormOut])
async def list_forms(principal: Configurer, module: Module) -> list[SupportFormOut]:
    return [
        SupportFormOut(
            key=f.key, kind=f.kind, label=f.label, fields=f.fields, enabled=f.enabled, version=f.version
        )
        for f in await module.definitions.forms(enabled_only=False)
    ]


@router.put("/admin/support/forms/{key}", response_model=SupportFormOut)
async def put_form(principal: Configurer, key: str, body: SupportFormIn, module: Module) -> SupportFormOut:
    f = await module.definitions.save_form(
        principal, key[:60], body.kind, body.label, body.fields, body.enabled
    )
    return SupportFormOut(
        key=f.key, kind=f.kind, label=f.label, fields=f.fields, enabled=f.enabled, version=f.version
    )
