"""AI diagnosis (T034; R11): Support defines the steps, the AI capability (018) provides only the
interpretation (``support.diagnosis_executor``), run **as the requesting user**:

1. identify the user · 2. service state (006) · 3. open incidents · 4. wiki pages the user may read and the
assistant may use — all **real data** with ``as_of``; 5. analyze · 6. propose — **AI interpretation**,
labelled as such; 7. prefill a ``ticket_draft`` (never a ticket: the user reviews and submits).
Without an executor, or when it fails, the diagnosis answers 503 and the manual path is untouched."""

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from uuid import UUID

from portalab.capabilities.content import KNOWLEDGE
from portalab.capabilities.health import SERVICE_STATE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.support import DIAGNOSIS, DiagnosisFacts
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound, Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.support.models import DiagnosisRun, TicketDraft
from portalab.modules.support.precheck.service import Precheck


class DiagnosisUnavailable(Unavailable):
    default_code = "diagnosis.unavailable"
    default_title = "The assistant cannot run a diagnosis right now"


class DraftNotFound(NotFound):
    default_code = "ticket.draft_not_found"
    default_title = "Draft not found"


class DiagnosisOrchestrator:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        precheck: Precheck,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.precheck = precheck
        self.config = config  # callable → SupportConfig
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def ensure_available(self) -> None:
        if self._port(DIAGNOSIS) is None:
            raise DiagnosisUnavailable(
                "The assistant is not available; you can still open a ticket yourself."
            )

    def _step(
        self, name: str, kind: str, status: str, data: dict[str, Any], refs: list[str] | None = None
    ) -> dict[str, Any]:
        return {
            "name": name,
            "kind": kind,
            "status": status,
            "data": data,
            "refs": refs or [],
            "as_of": utc_now(self.clock).isoformat(),
        }

    async def run(
        self, principal: Principal, problem: str, service_id: str | None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields each step as it completes, then ``{"done": …}``. Steps are stored on the run."""
        self.ensure_available()
        user = principal.acting_for or principal.user_id
        assert user is not None
        steps: list[dict[str, Any]] = []
        async with self.database.unit_of_work() as uow:
            run = DiagnosisRun(user_id=user, steps=[], outcome="running", created_at=utc_now(self.clock))
            uow.session.add(run)
            await uow.session.flush()
            run_id = run.id

        async def emit(step: dict[str, Any]) -> dict[str, Any]:
            steps.append(step)
            return step

        yield await emit(self._step("identify_user", "real", "ok", {"user": str(user)}))
        service: dict[str, Any] | None = None
        if service_id:
            reader = self._port(SERVICE_STATE)
            try:
                state = await asyncio.wait_for(reader.get(service_id), timeout=3) if reader else None
            except Exception:
                state = None
            as_of = getattr(state, "as_of", None)
            service = {
                "service_id": service_id,
                "state": getattr(state, "state", "unknown"),
                "as_of": as_of.isoformat() if as_of is not None else None,
            }
            yield await emit(
                self._step(
                    "service_state",
                    "real",
                    "ok" if state else "unavailable",
                    service,
                    [f"service:{service_id}"],
                )
            )
        incidents = await self.precheck.incidents_for(principal, service_id, problem)
        yield await emit(
            self._step(
                "open_incidents",
                "real",
                incidents["state"],
                incidents,
                [i["url"] for i in incidents["items"]],
            )
        )
        wiki: list[dict[str, Any]] = []
        knowledge = self._port(KNOWLEDGE)
        if knowledge is not None:
            try:
                hits = await asyncio.wait_for(
                    knowledge.search(problem, principal, limit=5, for_ai=True), timeout=3
                )
                wiki = [{"title": h.title, "excerpt": h.excerpt, "url": h.url} for h in hits]
                yield await emit(
                    self._step("search_wiki", "real", "ok", {"items": wiki}, [h.ref for h in hits])
                )
            except Exception:
                yield await emit(self._step("search_wiki", "real", "unavailable", {"items": []}))
        else:
            yield await emit(self._step("search_wiki", "real", "unavailable", {"items": []}))
        facts = DiagnosisFacts(
            problem=problem[:4000], service=service, open_incidents=incidents["items"], wiki=wiki
        )
        executor = self._port(DIAGNOSIS)
        try:
            analysis = await asyncio.wait_for(executor.analyze(facts, principal), timeout=60)  # type: ignore[union-attr]
        except Exception as exc:
            yield await emit(self._step("analyze", "ai", "failed", {}))
            await self._finish(run_id, steps, "failed")
            raise DiagnosisUnavailable("The assistant failed; you can still open a ticket yourself.") from exc
        yield await emit(self._step("analyze", "ai", "ok", {"summary": analysis.summary}))
        yield await emit(self._step("propose", "ai", "ok", {"solution": analysis.proposed_solution}))
        draft_id: UUID | None = None
        outcome = "resolved" if analysis.solved else "ticket_prefilled"
        if not analysis.solved:
            payload = {
                "type_key": analysis.suggested_type or "other",
                "title": (analysis.suggested_title or problem.splitlines()[0])[:200],
                "description": f"{problem}\n\n{analysis.summary}".strip(),
                "fields": dict(analysis.suggested_fields),
                "service_id": service_id,
            }
            async with self.database.unit_of_work() as uow:
                draft = TicketDraft(
                    user_id=user,
                    payload=payload,
                    source="ai",
                    diagnosis_run_id=run_id,
                    expires_at=utc_now(self.clock)
                    + timedelta(minutes=max(1, self.config().draft_ttl_minutes)),
                    created_at=utc_now(self.clock),
                )
                uow.session.add(draft)
                await uow.session.flush()
                draft_id = draft.id
            yield await emit(self._step("prefill_ticket_draft", "real", "ok", {"draft": str(draft_id)}))
        await self._finish(run_id, steps, outcome)
        yield {
            "done": True,
            "run": str(run_id),
            "outcome": outcome,
            "draft": str(draft_id) if draft_id else None,
        }

    async def _finish(self, run_id: UUID, steps: list[dict[str, Any]], outcome: str) -> None:
        async with self.database.unit_of_work() as uow:
            run = await uow.session.get(DiagnosisRun, run_id, with_for_update=True)
            if run is not None:
                run.steps, run.outcome = steps, outcome

    async def get_run(self, principal: Principal, run_id: UUID) -> DiagnosisRun:
        async with self.database.session() as session:
            run = await session.get(DiagnosisRun, run_id)
        if run is None or run.user_id != (principal.acting_for or principal.user_id):
            raise NotFound("This diagnosis does not exist.", code="diagnosis.not_found")
        return run

    async def get_draft(self, principal: Principal, draft_id: UUID) -> TicketDraft:
        async with self.database.session() as session:
            draft = await session.get(TicketDraft, draft_id)
        if (
            draft is None
            or draft.user_id != (principal.acting_for or principal.user_id)
            or draft.expires_at < utc_now(self.clock)
        ):
            raise DraftNotFound("This draft does not exist or has expired.")
        return draft

    async def consume_draft(self, draft_id: UUID) -> None:
        from sqlalchemy import delete

        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(TicketDraft).where(TicketDraft.id == draft_id))

    async def purge(self) -> int:
        from sqlalchemy import delete

        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(TicketDraft).where(TicketDraft.expires_at < utc_now(self.clock))
            )
            return int(getattr(result, "rowcount", 0) or 0)
