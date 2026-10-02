"""Optional Prometheus-format ``/metrics`` endpoint (T032; R2): **disabled by default**. When enabled it
answers to a bearer token configured as the write-only ``observability.metricsToken`` setting, or to a
signed-in holder of ``observability.read``. It renders the latest minute samples and component health."""

import hmac
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core.authorization import current_principal, public
from portalab.core.errors import NotFound, Unauthorized
from portalab.modules.observability.api.routes import observability_module
from portalab.modules.observability.models import ComponentHealth, MetricSample
from portalab.modules.observability.permissions import OBSERVABILITY_READ
from portalab.modules.observability.settings import METRICS_TOKEN

router = APIRouter(tags=["observability"])
_NAME = re.compile(r"[^a-zA-Z0-9_]")
_LEVEL = {"ok": 0, "degraded": 1, "unknown": 2, "down": 3, "failing": 3}


def _metric(name: str) -> str:
    return "portalab_" + _NAME.sub("_", name).strip("_").lower()


def _labels(labels: dict[str, Any]) -> str:
    if not labels:
        return ""
    escaped = ",".join(
        f'{_NAME.sub("_", k)}="{str(v).replace(chr(34), "")}"' for k, v in sorted(labels.items())
    )
    return "{" + escaped + "}"


async def _authorized(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        providers = request.app.state.capabilities.system_providers(CONFIG)
        token = (await providers[0].provider.get(METRICS_TOKEN)).value if providers else None
        return bool(token) and hmac.compare_digest(str(token), header[7:].strip())
    principal = await current_principal(request)
    if not principal.is_authenticated:
        return False
    return bool(await request.app.state.authorizer.is_allowed(principal, OBSERVABILITY_READ, None))


@router.get("/metrics", response_class=PlainTextResponse)
@public
async def metrics_endpoint(request: Request) -> PlainTextResponse:
    module = observability_module(request)
    if not module.config.metrics_endpoint_enabled:
        raise NotFound()
    if not await _authorized(request):
        raise Unauthorized("A metrics token or the observability.read permission is required.")
    lines: list[str] = []
    async with module.database.session() as session:
        latest = await session.scalar(select(func.max(MetricSample.sampled_at)))
        if latest is not None:
            for row in (
                await session.execute(select(MetricSample).where(MetricSample.sampled_at == latest))
            ).scalars():
                name = _metric(f"{row.component}_{row.metric}")
                labels = _labels(dict(row.labels))
                lines.append(f"{name}_count{labels} {row.count}")
                lines.append(f"{name}_sum{labels} {row.sum}")
        for health in (await session.execute(select(ComponentHealth))).scalars():
            for axis in ("technical", "functional"):
                state = getattr(health, axis)
                labels = _labels({"component": health.component, "axis": axis})
                lines.append(f"portalab_component_health{labels} {_LEVEL.get(state, 2)}")
    stats = module.metrics_registry.stats()
    lines.append(f"portalab_observability_queue_depth {stats['depth']}")
    lines.append(f"portalab_observability_dropped_total {stats['dropped']}")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
