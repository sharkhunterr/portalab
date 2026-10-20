"""AI module facade (spec 018): a bounded assistant acting for the user.

Observability's ``ai`` component is fed by ``report_ai_call`` (metadata only) at the end of every turn.
Builds the tool catalog (registry + Admin-allow-listed MCP tools), executor, pending actions, orchestrator,
conversations and governor; registers the baseline read tools, and — **only while the assistant is
available** — the facades other specs consume: ``search.assistant`` (008), ``support.diagnosis_executor``
(016), ``ai.invoke`` (019) and, when configured, ``search.embedding`` (008). When the assistant is off or
unconfigured they are withdrawn, so every consumer falls back to its classic path."""

from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import timedelta
from typing import Any

import httpx

from portalab.capabilities.ai import INVOKE, MODELS, AIToolRegistry, LLMProvider, ModelInfo, default_ai_tools
from portalab.capabilities.automation_actions import ActionRegistry, ActionType, default_actions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.i18n import RESOLVER, SITE_TERMS
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.navigation import NavigationRegistry, default_navigation
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.search import ASSISTANT, EMBEDDING, SearchRegistry, default_search
from portalab.capabilities.support import DIAGNOSIS
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock
from portalab.modules.ai import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.ai.chat import ChatService
from portalab.modules.ai.conversations import Conversations
from portalab.modules.ai.events import register_event_types
from portalab.modules.ai.executor import ToolExecutor
from portalab.modules.ai.external.mcp import McpToolset
from portalab.modules.ai.facades.automation import AutomationInvoker
from portalab.modules.ai.facades.diagnosis import DiagnosisFacade
from portalab.modules.ai.facades.embeddings import OpenAICompatibleEmbeddings
from portalab.modules.ai.facades.search_assistant import SearchAssistantFacade
from portalab.modules.ai.governor import Governor
from portalab.modules.ai.insights import Insights
from portalab.modules.ai.observability import log
from portalab.modules.ai.orchestrator import Orchestrator
from portalab.modules.ai.participant import AiParticipant
from portalab.modules.ai.pending import PendingActions
from portalab.modules.ai.providers.openai_compat import OpenAICompatibleProvider
from portalab.modules.ai.settings import API_KEY, MCP_TOKENS, SETTINGS, AiConfig
from portalab.modules.ai.tools.baseline import BaselineTools
from portalab.modules.ai.tools.catalog import ToolCatalog

OWNER = "module:ai"
INSTANCE = "ai"
EXPIRE_JOB = "ai.pending_expire"
PURGE_JOB = "ai.conversations_purge"


class AiModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        tools: AIToolRegistry = default_ai_tools,
        event_types: EventTypeRegistry = default_event_types,
        search: SearchRegistry = default_search,
        navigation: NavigationRegistry = default_navigation,
        actions: ActionRegistry = default_actions,
    ) -> None:
        self.actions = actions
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.tools = tools
        self.event_types = event_types
        self.config = AiConfig()
        self.api_key: str | None = None
        self.mcp_tokens: dict[str, str] = {}
        self.provider_override: LLMProvider | None = None  # tests and future adapters
        self.transport: httpx.AsyncBaseTransport | None = None
        self.mcp = McpToolset(lambda: self.config.mcp_servers, lambda: self.mcp_tokens, clock=clock)
        self.catalog = ToolCatalog(
            authorizer,
            registry=tools,
            disabled=lambda: self.config.tools_disabled,
            external=self.mcp.tools,
            refresh=self.mcp.refresh,
        )
        self.pending = PendingActions(
            database, events, audit, capabilities, lambda: self.config.pending_action_ttl_minutes, clock=clock
        )
        self.executor = ToolExecutor(authorizer, self.pending)
        self.pending.runner = self.executor
        self.pending.resolve_tool = lambda name: next((t for t in self.catalog.all() if t.name == name), None)
        self.orchestrator = Orchestrator(
            self.provider,
            self.catalog,
            self.executor,
            lambda: self.config,
            language=self._language,
            who=self._who,
            site=self._site,
            secrets=lambda: (self.api_key, *self.mcp_tokens.values()),
        )
        self.conversations = Conversations(database, events, clock=clock)
        self.governor = Governor(database, lambda: self.config, clock=clock)
        self.chat = ChatService(self.conversations, self.governor, self.orchestrator)
        self.insights = Insights(database, capabilities, clock=clock)  # issue 176: verdicts and dashboard
        self.baseline = BaselineTools(
            capabilities, authorizer, search=search, navigation=navigation, clock=clock
        )
        self.facades: dict[str, Any] = {
            ASSISTANT: SearchAssistantFacade(self.orchestrator, search),
            DIAGNOSIS: DiagnosisFacade(self.orchestrator),
            INVOKE: AutomationInvoker(self.orchestrator),
        }

    # --- provider -------------------------------------------------------------------------------------
    def provider(self) -> LLMProvider | None:
        if not self.config.enabled:
            return None
        if self.provider_override is not None:
            return self.provider_override
        if not self.config.provider_endpoint or not self.config.provider_model:
            return None
        return OpenAICompatibleProvider(
            self.config.provider_endpoint,
            self.config.provider_model,
            lambda: self.api_key,
            transport=self.transport,
            max_context=self.config.max_context_tokens,
            reasoning=self.config.provider_reasoning,
        )

    def available(self) -> bool:
        return self.provider() is not None

    async def servers(self) -> list[dict[str, Any]]:
        """Issue 169: the model servers the connected services offer (Ollama) — their address for the
        assistant, their models and those in memory; a server that does not answer says so."""
        try:
            registrations = self.capabilities.system_providers(MODELS)
        except Exception:
            return []
        found: list[dict[str, Any]] = []
        for registration in registrations:
            meta = registration.metadata
            entry: dict[str, Any] = {
                "service_id": str(meta.get("service_id") or registration.instance_ref),
                "name": str(meta.get("name") or registration.instance_ref),
                "connector": str(meta.get("connector") or ""),
                "endpoint": "",
                "models": [],
                "state": "ok",
            }
            try:
                entry["endpoint"] = str(registration.provider.endpoint())
                answer = await registration.provider.models()
                models: list[ModelInfo] = list(getattr(answer, "value", answer) or [])
                if not getattr(answer, "has_data", True):
                    entry["state"] = str(getattr(answer, "state", "unavailable"))
                entry["models"] = [asdict(m) for m in models if isinstance(m, ModelInfo)]
            except Exception:
                entry["state"] = "unavailable"
            found.append(entry)
        return found

    def _site(self, language: str) -> str | None:
        """Issues 159/171: the site's own name, else none — the prompt then says « this portal »."""
        providers = self.capabilities.system_providers(SITE_TERMS)
        return providers[0].provider.terms(language).name if providers else None

    async def _who(self, user: Any) -> str | None:
        """Issue 171: the member's display name, for the assistant to know whom it speaks with."""
        providers = self.capabilities.system_providers(DIRECTORY)
        if not providers:
            return None
        summary = await providers[0].provider.get_user_summary(user)
        return summary.display_name if summary is not None else None

    async def _language(self, user: Any) -> str:
        providers = self.capabilities.system_providers(RESOLVER)
        if not providers:
            return "en"
        return str((await providers[0].provider.for_user(user)).language)

    # --- registration ---------------------------------------------------------------------------------
    def register(self) -> None:
        register_event_types(self.event_types)
        self.baseline.register(self.tools)
        participant = AiParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref=INSTANCE, owner=OWNER)
        default_retention_targets.register(
            RetentionTarget(
                "ai.conversations",
                "ai.conversations",
                "personal",
                "updated_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=max(1, self.config.retention_days)),
            )
        )
        self.sync_facades()
        if self.actions.get("ai.invoke") is None:
            invoker = self.facades[INVOKE]

            async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
                text = await invoker.invoke(
                    str(params["instruction"])[:4000],
                    principal,
                    max_tokens=int(params.get("max_tokens", 400)),
                )
                return {"text": text}

            self.actions.register(
                ActionType(
                    key="ai.invoke",
                    description="Draft, summarize or classify text with the assistant (assist only)",
                    permission="ai.use",
                    idempotency="no side effect: produces text for later steps",
                    run=run,
                    owner=OWNER,
                    params_schema={"instruction": "string", "max_tokens": "integer?"},
                )
            )

    def sync_facades(self) -> None:
        """Facades exist only while the assistant can answer; consumers then use their classic paths."""
        available = self.available()
        for name, facade in self.facades.items():
            present = any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(name))
            if available and not present and not self.capabilities.system_providers(name):
                self.capabilities.provide(name, facade, instance_ref=INSTANCE, owner=OWNER)
            elif not available and present:
                self.capabilities.withdraw(name, INSTANCE)
        embedding = any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(EMBEDDING))
        wanted = available and bool(self.config.embeddings_model) and self.config.embeddings_dimension > 0
        if embedding and not wanted:
            self.capabilities.withdraw(EMBEDDING, INSTANCE)
        elif wanted and not embedding and not self.capabilities.system_providers(EMBEDDING):
            self.capabilities.provide(
                EMBEDDING,
                OpenAICompatibleEmbeddings(
                    lambda: self.config.provider_endpoint,
                    self.config.embeddings_model,
                    self.config.embeddings_dimension,
                    lambda: self.api_key,
                    transport=self.transport,
                ),
                instance_ref=INSTANCE,
                owner=OWNER,
            )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def expire() -> None:
            await self.pending.expire()

        async def purge() -> None:
            await self.conversations.purge(self.config.retention_days)

        return [
            self.start,
            register_periodic(jobs, self.database, EXPIRE_JOB, timedelta(minutes=1), expire, owner=OWNER),
            register_periodic(jobs, self.database, PURGE_JOB, timedelta(hours=6), purge, owner=OWNER),
        ]

    async def start(self) -> None:
        await self.refresh_config()

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                reader = providers[0].provider
                values = {name: (await reader.get(key)).value for name, key in SETTINGS.items()}
                self.config = replace(self.config, **values)
                self.api_key = (await reader.get(API_KEY)).value or None
                self.mcp_tokens = dict((await reader.get(MCP_TOKENS)).value or {})
        except Exception:
            log.warning("ai configuration not refreshed")
        self.sync_facades()
