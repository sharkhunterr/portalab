"""Terms of use API (027): the version in force (028: once signed in), the member's own
standing and acceptance, and the administrators' publication with the history of versions."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.privacy.api.routes import Module
from portalab.modules.privacy.models import TermsVersion
from portalab.modules.privacy.permissions import TERMS_MANAGE
from portalab.modules.privacy.terms.service import TermsStatus

router = APIRouter(prefix="/api/v1", tags=["terms"])


class TermsOut(BaseModel):
    version: int
    title: str
    summary: str
    html: str
    requires_acceptance: bool
    published_at: datetime


class TermsEditorOut(TermsOut):
    body_md: str
    acceptances: int


class TermsPublic(BaseModel):
    terms: TermsOut | None


class MyTermsOut(BaseModel):
    terms: TermsOut | None
    accepted_version: int | None
    accepted_at: datetime | None
    required: bool


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=1000)
    body_md: str = Field(min_length=1, max_length=200_000)
    requires_acceptance: bool = True


class TermsAdminOut(BaseModel):
    versions: list[TermsEditorOut]
    members_up_to_date: int
    enabled: bool  # optional: off, members are asked nothing (the versions stay)


class EnforcementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def _out(version: TermsVersion) -> TermsOut:
    return TermsOut(
        version=version.version,
        title=version.title,
        summary=version.summary,
        html=version.body_html,
        requires_acceptance=version.requires_acceptance,
        published_at=version.published_at,
    )


def _mine(standing: TermsStatus) -> MyTermsOut:
    return MyTermsOut(
        terms=_out(standing.current) if standing.current else None,
        accepted_version=standing.accepted_version,
        accepted_at=standing.accepted_at,
        required=standing.required,
    )


@router.get("/terms", response_model=TermsPublic)
async def current_terms(_: Annotated[Principal, require("users.self.manage")], module: Module) -> TermsPublic:
    """028: read once signed in (the acceptance gate shows them): nothing answers a visitor but sign-in."""
    current = await module.terms.current() if await module.terms.enabled() else None
    return TermsPublic(terms=_out(current) if current else None)


@router.get("/me/terms", response_model=MyTermsOut)
async def my_terms(module: Module, principal: Principal = require("users.self.manage")) -> MyTermsOut:
    assert principal.user_id is not None
    return _mine(await module.terms.status(principal.user_id))


@router.post(
    "/me/terms/accept", response_model=MyTermsOut, responses={409: {"description": "terms.outdated"}}
)
async def accept_terms(
    body: AcceptIn, module: Module, principal: Principal = require("users.self.manage")
) -> MyTermsOut:
    assert principal.user_id is not None
    return _mine(await module.terms.accept(principal.user_id, body.version))


@router.get("/admin/terms", response_model=TermsAdminOut)
async def terms_history(module: Module, _: Principal = require(TERMS_MANAGE)) -> TermsAdminOut:
    history = await module.terms.history()
    versions = [
        TermsEditorOut(
            **_out(entry.version).model_dump(), body_md=entry.version.body_md, acceptances=entry.acceptances
        )
        for entry in history
    ]
    return TermsAdminOut(
        versions=versions,
        members_up_to_date=await module.terms.up_to_date(),
        enabled=await module.terms.enabled(),
    )


@router.put("/admin/terms/enforcement", status_code=status.HTTP_204_NO_CONTENT)
async def set_terms_enforcement(
    body: EnforcementIn, module: Module, principal: Principal = require(TERMS_MANAGE)
) -> Response:
    await module.terms.set_enabled(principal, body.enabled)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/terms", response_model=TermsOut, status_code=status.HTTP_201_CREATED)
async def publish_terms(
    body: PublishIn, module: Module, principal: Principal = require(TERMS_MANAGE)
) -> TermsOut:
    published = await module.terms.publish(
        principal,
        title=body.title,
        summary=body.summary,
        body_md=body.body_md,
        requires_acceptance=body.requires_acceptance,
    )
    return _out(published)
