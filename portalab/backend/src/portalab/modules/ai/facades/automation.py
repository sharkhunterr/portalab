"""``ai.invoke`` for 019 (T035; F12): read-only text drafting/classification as the automation's
principal (acting for its author). Read tools only, no pending actions, a capped plain-text answer; the
automation engine uses it to fill text fields — never as a condition nor in sensitive parameters."""

from portalab.capabilities.ai import ChatMessage
from portalab.core.authz_port import Principal
from portalab.modules.ai.context import system_prompt
from portalab.modules.ai.orchestrator import Orchestrator
from portalab.modules.ai.principal import subject_of
from portalab.modules.ai.tools.catalog import READ_ONLY

MAX_TEXT = 4000


class AutomationInvoker:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def invoke(self, instruction: str, principal: Principal, *, max_tokens: int = 400) -> str:
        language = await self.orchestrator.language_for(subject_of(principal))
        messages = [
            ChatMessage("system", system_prompt(language, None) + "\nAnswer with plain text only."),
            ChatMessage("user", instruction[:4000]),
        ]
        outcome = await self.orchestrator.complete(principal, messages, policy=READ_ONLY)
        return outcome.content[: min(MAX_TEXT, max(1, max_tokens) * 4)]
