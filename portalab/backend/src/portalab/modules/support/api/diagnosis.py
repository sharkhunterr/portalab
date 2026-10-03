"""Diagnosis API (Slice B, R11): ``POST /diagnosis/runs`` streams the steps (Server-Sent Events) — real data
vs AI interpretation labelled; the outcome is at most a draft the user reviews. 503 when the assistant is
unavailable; the manual ticket path is unaffected."""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import PortalError
from portalab.modules.support.api.incidents import support_module
from portalab.modules.support.module import SupportModule

router = APIRouter(prefix="/api/v1", tags=["support"])
Module = Annotated[SupportModule, Depends(support_module)]
Requester = Annotated[Principal, require("tickets.create")]


class SupportDiagnosisIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem: str = Field(min_length=3, max_length=4000)
    service_id: str | None = Field(default=None, max_length=64)


class SupportDiagnosisRunOut(BaseModel):
    id: UUID
    outcome: str
    steps: list[dict[str, Any]]
    created_at: datetime


class TicketDraftOut(BaseModel):
    id: UUID
    payload: dict[str, Any]
    diagnosis_run_id: UUID | None
    expires_at: datetime


@router.post("/diagnosis/runs", response_class=StreamingResponse)
async def start(principal: Requester, body: SupportDiagnosisIn, module: Module) -> StreamingResponse:
    module.diagnosis.ensure_available()  # 503 before streaming when there is no assistant

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for step in module.diagnosis.run(principal, body.problem, body.service_id):
                name = "done" if step.get("done") else "step"
                yield f"event: {name}\ndata: {json.dumps(step, default=str)}\n\n".encode()
        except PortalError as exc:
            yield f"event: error\ndata: {json.dumps({'code': exc.code, 'detail': exc.detail})}\n\n".encode()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@router.get("/diagnosis/runs/{run_id}", response_model=SupportDiagnosisRunOut)
async def get_run(principal: Requester, run_id: UUID, module: Module) -> SupportDiagnosisRunOut:
    run = await module.diagnosis.get_run(principal, run_id)
    return SupportDiagnosisRunOut(id=run.id, outcome=run.outcome, steps=run.steps, created_at=run.created_at)


@router.get("/tickets/drafts/{draft_id}", response_model=TicketDraftOut)
async def get_draft(principal: Requester, draft_id: UUID, module: Module) -> TicketDraftOut:
    draft = await module.diagnosis.get_draft(principal, draft_id)
    return TicketDraftOut(
        id=draft.id,
        payload=draft.payload,
        diagnosis_run_id=draft.diagnosis_run_id,
        expires_at=draft.expires_at,
    )
