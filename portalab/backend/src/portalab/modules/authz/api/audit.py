"""Audit viewer API (T021): ``GET /audit`` (paginated) and ``GET /audit/export`` (NDJSON), ``audit.read``."""

import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.authz.api.routes import Module
from portalab.modules.authz.audit.query import AuditFilters

router = APIRouter(prefix="/api/v1", tags=["audit"])


class AuditPage(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None


def _filters(
    action: str | None,
    actor_user_id: UUID | None,
    resource_type: str | None,
    resource_id: str | None,
    decision: str | None,
    since: datetime | None,
    until: datetime | None,
) -> AuditFilters:
    return AuditFilters(action, actor_user_id, resource_type, resource_id, decision, since, until)


Decision = Literal["allow", "deny", "n/a"]


@router.get("/audit", response_model=AuditPage)
async def search_audit(
    module: Module,
    action: Annotated[str | None, Query(max_length=128)] = None,
    actor_user_id: UUID | None = None,
    resource_type: Annotated[str | None, Query(max_length=64)] = None,
    resource_id: Annotated[str | None, Query(max_length=128)] = None,
    decision: Decision | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
    principal: Principal = require("audit.read"),
) -> AuditPage:
    filters = _filters(action, actor_user_id, resource_type, resource_id, decision, since, until)
    items, next_cursor = await module.audit_query.search(principal, filters, limit=limit, cursor=cursor)
    return AuditPage(items=items, next_cursor=next_cursor)


@router.get(
    "/audit/export",
    responses={200: {"content": {"application/x-ndjson": {"schema": {"type": "string"}}}}},
)
async def export_audit(
    module: Module,
    action: Annotated[str | None, Query(max_length=128)] = None,
    actor_user_id: UUID | None = None,
    resource_type: Annotated[str | None, Query(max_length=64)] = None,
    resource_id: Annotated[str | None, Query(max_length=128)] = None,
    decision: Decision | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    principal: Principal = require("audit.read"),
) -> Response:
    filters = _filters(action, actor_user_id, resource_type, resource_id, decision, since, until)
    rows = await module.audit_query.export(principal, filters)
    body = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    return Response(
        body,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="audit-export.ndjson"',
            "Cache-Control": "no-store",
        },
    )
