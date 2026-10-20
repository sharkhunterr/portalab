"""User API (T011, T017): status, owner-only conversations, the streaming turn (SSE) and pending actions.

``POST /ai/conversations/{id}/messages`` refuses *before* streaming (problem documents for unavailable,
rate limit, budget), then streams ``delta``, ``tool_call``, ``tool_result``, ``source``,
``pending_action``, ``error`` and ``done``. Pending actions are confirmed only by their owner from a user
session (CSRF applies as for every mutating route); the AI can never reach these routes."""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.ai.errors import AiUnavailable
from portalab.modules.ai.models import Conversation, Message
from portalab.modules.ai.module import AiModule
from portalab.modules.ai.pending import PendingView
from portalab.modules.ai.permissions import AI_USE

router = APIRouter(prefix="/api/v1", tags=["ai"])


def ai_module(request: Request) -> AiModule:
    module = getattr(request.app.state, "ai_module", None)
    if not isinstance(module, AiModule):
        raise AiUnavailable("The assistant is not available.")
    return module


Module = Annotated[AiModule, Depends(ai_module)]
User = Annotated[Principal, require(AI_USE)]


class AiStatusOut(BaseModel):
    available: bool
    provider_state: str
    auto_navigate: bool
    name: str = ""  # issue 171: the assistant's name, as the settings say
    # issue 171: what is left of the member's daily allowance (tokens), for the window to show
    daily_budget: int = 0
    used_today: int = 0
    ideas: list[str] = Field(default_factory=list)  # issue 174: the administrators' questions to start with


class AiPageContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    help_key: str | None = Field(default=None, max_length=200)


class AiConversationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: AiPageContext | None = None


class AiConversationOut(BaseModel):
    id: UUID
    title: str
    context: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AiMessageOut(BaseModel):
    seq: int
    role: str
    content: str
    blocks: dict[str, Any]
    created_at: datetime


class AiConversationDetailOut(AiConversationOut):
    messages: list[AiMessageOut]


class AiMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=4000)
    # issue 171: the page the member asks from (a conversation goes on across pages)
    context: AiPageContext | None = None


class AiActionOut(BaseModel):
    id: UUID
    tool: str
    summary: str
    status: str
    expires_at: datetime
    created_at: datetime
    conversation_id: UUID | None
    result: dict[str, Any] | None


class AiToolOut(BaseModel):
    name: str
    description: str
    sensitivity: str


def _conversation(row: Conversation) -> AiConversationOut:
    return AiConversationOut(
        id=row.id, title=row.title, context=row.context, created_at=row.created_at, updated_at=row.updated_at
    )


def _message(row: Message) -> AiMessageOut:
    return AiMessageOut(
        seq=row.seq, role=row.role, content=row.content, blocks=row.blocks, created_at=row.created_at
    )


def _action(view: PendingView) -> AiActionOut:
    return AiActionOut(
        id=view.id,
        tool=view.tool,
        summary=view.summary,
        status=view.status,
        expires_at=view.expires_at,
        created_at=view.created_at,
        conversation_id=view.conversation_id,
        result=dict(view.result) if view.result else None,
    )


@router.get("/ai/status", response_model=AiStatusOut)
async def status(principal: User, module: Module) -> AiStatusOut:
    if not module.config.enabled:
        state = "disabled"
    elif not module.available():
        state = "not_configured"
    else:
        state = "ok"
    return AiStatusOut(
        available=state == "ok",
        provider_state=state,
        auto_navigate=module.config.auto_navigate,
        name=module.config.assistant_name,
        daily_budget=module.config.daily_token_budget_per_user,
        ideas=[i for i in module.config.assistant_ideas if isinstance(i, str) and i.strip()][:8],
        used_today=await _used(module, principal),
    )


async def _used(module: AiModule, principal: Principal) -> int:
    user = principal.acting_for or principal.user_id
    if user is None:
        return 0
    try:
        return await module.governor.used_today(user)
    except Exception:
        return 0


@router.get("/ai/tools", response_model=list[AiToolOut])
async def tools(principal: User, module: Module) -> list[AiToolOut]:
    offered = await module.catalog.for_principal(principal)
    return [
        AiToolOut(name=t.name, description=t.description, sensitivity=t.sensitivity) for t in offered.values()
    ]


@router.post("/ai/conversations", response_model=AiConversationOut, status_code=201)
async def create_conversation(principal: User, body: AiConversationIn, module: Module) -> AiConversationOut:
    context = body.context.model_dump(exclude_none=True) if body.context else None
    return _conversation(await module.conversations.create(principal, "", context))


@router.get("/ai/conversations", response_model=list[AiConversationOut])
async def list_conversations(principal: User, module: Module) -> list[AiConversationOut]:
    return [_conversation(row) for row in await module.conversations.owned_list(principal)]


@router.get("/ai/conversations/{conversation_id}", response_model=AiConversationDetailOut)
async def get_conversation(principal: User, conversation_id: UUID, module: Module) -> AiConversationDetailOut:
    row = await module.conversations.owned(principal, conversation_id)
    messages = [_message(m) for m in await module.conversations.messages(conversation_id)]
    return AiConversationDetailOut(**_conversation(row).model_dump(), messages=messages)


@router.delete("/ai/conversations/{conversation_id}", status_code=204)
async def delete_conversation(principal: User, conversation_id: UUID, module: Module) -> Response:
    await module.conversations.delete(principal, conversation_id)
    return Response(status_code=204)


@router.post("/ai/conversations/{conversation_id}/messages", response_class=StreamingResponse)
async def send_message(
    principal: User, conversation_id: UUID, body: AiMessageIn, module: Module
) -> StreamingResponse:
    page = body.context.model_dump(exclude_none=True) if body.context else None
    turn = await module.chat.prepare(principal, conversation_id, body.content, page=page)

    async def stream() -> AsyncIterator[bytes]:
        async for item in module.chat.events(turn):
            payload = json.dumps(item["data"], default=str, ensure_ascii=False)
            yield f"event: {item['event']}\ndata: {payload}\n\n".encode()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/ai/actions/{action_id}", response_model=AiActionOut)
async def get_action(principal: User, action_id: UUID, module: Module) -> AiActionOut:
    return _action(await module.pending.get(principal, action_id))


@router.post("/ai/actions/{action_id}/confirm", response_model=AiActionOut)
async def confirm_action(principal: User, action_id: UUID, module: Module) -> AiActionOut:
    return _action(await module.pending.confirm(principal, action_id))


@router.post("/ai/actions/{action_id}/decline", response_model=AiActionOut)
async def decline_action(principal: User, action_id: UUID, module: Module) -> AiActionOut:
    return _action(await module.pending.decline(principal, action_id))
