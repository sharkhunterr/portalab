"""``support.diagnosis_executor`` for 016 (T028): interprets the facts Support gathered (already limited
to what the user may see) with **no tools** — it never acts, never submits a ticket; it only returns an
analysis labelled as AI interpretation. Any failure raises, and Support falls back to the manual path."""

import json
import re
from typing import Any

from portalab.capabilities.ai import ChatMessage, ToolResult
from portalab.capabilities.support import DiagnosisAnalysis, DiagnosisFacts
from portalab.core.authz_port import Principal
from portalab.modules.ai.context import frame_tool_result, system_prompt
from portalab.modules.ai.errors import AiUnavailable
from portalab.modules.ai.orchestrator import Orchestrator
from portalab.modules.ai.principal import subject_of
from portalab.modules.ai.tools.catalog import NO_TOOLS

JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
TYPES = ("bug", "access_request", "service_issue", "question", "other")
INSTRUCTION = (
    "Analyze the user's problem from the facts below. Answer ONLY with a JSON object with keys: "
    "summary (string), proposed_solution (string), "
    "solved (boolean, true only if the facts clearly solve it), "
    "suggested_title (string), suggested_type (one of " + ", ".join(TYPES) + ")."
)


class DiagnosisFacade:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def analyze(self, facts: DiagnosisFacts, principal: Principal) -> DiagnosisAnalysis:
        data = {
            "problem": facts.problem,
            "service": dict(facts.service) if facts.service else None,
            "open_incidents": [dict(i) for i in facts.open_incidents][:10],
            "wiki": [dict(w) for w in facts.wiki][:5],
        }
        language = await self.orchestrator.language_for(subject_of(principal))
        messages = [
            ChatMessage("system", system_prompt(language, None)),
            ChatMessage(
                "user", INSTRUCTION + "\n" + frame_tool_result("diagnosis.facts", ToolResult("ok", data), [])
            ),
        ]
        outcome = await self.orchestrator.complete(principal, messages, policy=NO_TOOLS)
        return parse_analysis(outcome.content)


def parse_analysis(content: str) -> DiagnosisAnalysis:
    match = JSON_OBJECT.search(content)
    raw: Any = None
    if match is not None:
        try:
            raw = json.loads(match.group(0))
        except ValueError:
            raw = None
    if not isinstance(raw, dict):
        if not content.strip():
            raise AiUnavailable("The assistant gave no analysis.")
        return DiagnosisAnalysis(summary=content.strip()[:2000])
    kind = raw.get("suggested_type")
    return DiagnosisAnalysis(
        summary=str(raw.get("summary") or "")[:2000],
        proposed_solution=str(raw.get("proposed_solution") or "")[:2000],
        suggested_title=str(raw.get("suggested_title") or "")[:200],
        suggested_type=kind if kind in TYPES else "other",
        solved=raw.get("solved") is True,
    )
