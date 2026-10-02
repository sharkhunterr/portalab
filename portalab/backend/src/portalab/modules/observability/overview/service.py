"""Overview (T028; FR-023..025): an **action-first** list of problems, not a flat metric list.

Problems come from component health (any axis degraded/down/failing), open errors and undecided or
escalated anomalies. Ranking: (1) action needed, (2) impact, (3) criticality, (4) age (oldest first),
(5) details. Each problem carries ``DiagnosticAction`` descriptors that point to the owners' APIs.
The overview also feeds the Administration Control Center (panel + required actions)."""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from portalab.capabilities.administration import PanelResult, RequiredAction
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.observability.components.evaluator import reported_status
from portalab.modules.observability.models import Anomaly, ComponentHealth, ErrorRecord

_SEVERITY = {"info": 1, "warning": 2, "critical": 3}


def _diag(action: Any) -> dict[str, Any]:
    return {
        "key": action.key,
        "label": action.label,
        "method": action.method,
        "path": action.path,
        "permission": action.permission,
        "sensitive": action.sensitive,
    }


class OverviewService:
    def __init__(self, database: Database, registry: ObservableRegistry) -> None:
        self.database = database
        self.registry = registry

    async def problems(self, *, full_context: bool = True, limit: int = 50) -> list[dict[str, Any]]:
        declared = {c.name: c for c in await self.registry.components()}
        problems: list[dict[str, Any]] = []
        async with self.database.session() as session:
            health = (await session.execute(select(ComponentHealth))).scalars().all()
            errors = (
                (await session.execute(select(ErrorRecord).where(ErrorRecord.state != "resolved")))
                .scalars()
                .all()
            )
            anomalies = (
                (
                    await session.execute(
                        select(Anomaly).where(
                            Anomaly.status.in_(("candidate", "pending_validation", "escalated"))
                        )
                    )
                )
                .scalars()
                .all()
            )
        for row in health:
            unobserved = set(row.reason.get("unobserved", []))
            bad_technical = row.technical in ("degraded", "down") or (
                row.technical == "unknown" and "technical" not in unobserved
            )
            bad_functional = row.functional in ("degraded", "failing") or (
                row.functional == "unknown" and "functional" not in unobserved
            )
            if not (bad_technical or bad_functional) or row.component == "portal":
                continue
            component = declared.get(row.component)
            label = component.label if component else row.component
            severe = row.technical == "down" or row.functional == "failing"
            problems.append(
                {
                    "kind": "component",
                    "id": row.component,
                    "title": f"{label}: {reported_status(row.technical, row.functional)}",
                    "component": row.component,
                    "technical": row.technical,
                    "functional": row.functional,
                    "action_needed": severe,
                    "impact": component.impact if component else 1,
                    "criticality": (component.criticality if component else 1) + (2 if severe else 0),
                    "since": row.since,
                    "details": row.reason if full_context else {"unobserved": sorted(unobserved)},
                    "diagnostics": [_diag(a) for a in component.diagnostics] if component else [],
                }
            )
        for error in errors:
            component = declared.get(error.component)
            problems.append(
                {
                    "kind": "error",
                    "id": str(error.id),
                    "title": f"{error.component}: {error.category} x{error.count}",
                    "component": error.component,
                    "action_needed": error.state == "open",
                    "impact": component.impact if component else 1,
                    "criticality": 2 if error.level in ("error", "critical") else 1,
                    "since": error.first_seen_at,
                    "details": (
                        {"message": error.message, "context": error.context, "count": error.count}
                        if full_context
                        else {"count": error.count, "category": error.category}
                    ),
                    "diagnostics": [_diag(a) for a in component.diagnostics] if component else [],
                }
            )
        for anomaly in anomalies:
            problems.append(
                {
                    "kind": "anomaly",
                    "id": str(anomaly.id),
                    "title": f"{anomaly.detector.replace('_', ' ')} on {anomaly.component}",
                    "component": anomaly.component,
                    "action_needed": anomaly.status == "pending_validation",
                    "impact": declared[anomaly.component].impact if anomaly.component in declared else 1,
                    "criticality": _SEVERITY.get(anomaly.severity, 1),
                    "since": anomaly.detected_at,
                    "details": {
                        "status": anomaly.status,
                        "incident_ref": anomaly.incident_ref,
                        **({"evidence": anomaly.evidence} if full_context else {}),
                    },
                    "diagnostics": [
                        {
                            "key": "validate",
                            "label": "Validate (create or attach an incident)",
                            "method": "POST",
                            "path": f"/api/v1/admin/observability/anomalies/{anomaly.id}/validate",
                            "permission": "observability.manage",
                            "sensitive": True,
                        },
                        {
                            "key": "dismiss",
                            "label": "Dismiss",
                            "method": "POST",
                            "path": f"/api/v1/admin/observability/anomalies/{anomaly.id}/dismiss",
                            "permission": "observability.manage",
                            "sensitive": True,
                        },
                    ],
                }
            )
        problems.sort(
            key=lambda p: (not p["action_needed"], -p["impact"], -p["criticality"], p["since"], p["title"])
        )
        for problem in problems:
            if isinstance(problem["since"], datetime):
                problem["since"] = problem["since"].isoformat()
        return problems[:limit]

    async def portal_status(self) -> dict[str, Any]:
        async with self.database.session() as session:
            row = await session.get(ComponentHealth, "portal")
        if row is None:
            return {"status": "unknown"}
        return {"status": reported_status(row.technical, row.functional), "since": row.since.isoformat()}


class OverviewPanel:
    """Control Center panel (020): global status + top problems, or its own ``unavailable`` state."""

    def __init__(self, overview: OverviewService) -> None:
        self.overview = overview

    async def panel(self, principal: Principal) -> PanelResult:
        try:
            problems = await self.overview.problems(full_context=False, limit=5)
            status = await self.overview.portal_status()
        except Exception:
            return PanelResult("unavailable")
        return PanelResult(
            "available" if status["status"] != "unknown" else "no-data", {**status, "problems": problems}
        )


class ObservabilityRequiredActions:
    def __init__(self, overview: OverviewService) -> None:
        self.overview = overview

    async def items(self, principal: Principal) -> list[RequiredAction]:
        actions = []
        for problem in await self.overview.problems(full_context=False, limit=20):
            if not problem["action_needed"]:
                continue
            actions.append(
                RequiredAction(
                    id=f"observability:{problem['kind']}:{problem['id']}",
                    title_key=problem["title"],
                    impact=problem["impact"],
                    criticality=problem["criticality"],
                    since=datetime.fromisoformat(problem["since"]),
                    link="/admin/observability",
                )
            )
        return actions
