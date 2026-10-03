# AI assistant (spec 018)

The assistant is a **bounded agent acting for the signed-in user**. It reaches the portal only through
registered *tools*, each wrapping the same domain service the human API uses, and it never holds more rights
than the user. It is optional: when it is off, unconfigured or failing, every classic feature keeps working.

## How a turn works

1. `POST /api/v1/ai/conversations/{id}/messages` — the governor refuses *before* streaming when the assistant
   is off (`ai.unavailable`, 503), the user is too fast (`ai.rate_limited`, 429) or out of daily budget
   (`ai.budget_exceeded`, 429).
2. The orchestrator builds the context: the system policy, the user's language (026 `i18n.resolver`), the
   page the conversation was opened from, and a sliding window of the conversation within
   `ai.maxContextTokens`.
3. The tool catalog offered to the model is computed **per principal**: tools disabled by the Admin, not
   allowed by the turn policy, `ai_forbidden`, or not authorized for `Principal(channel="ai", acting_for=user)`
   are left out.
4. The provider streams text and tool calls (`delta`, `tool_call`). Every call goes through the executor:
   the tool must be in this turn's catalog (otherwise `ai.tool_forbidden`, revealing nothing), its
   parameters must validate against its JSON Schema, and the AI principal is **re-authorized** right before
   the call. `sensitive` tools never run inline: a pending action is created instead (`pending_action`).
5. Tool results are redacted (secret-looking keys masked), size-capped and handed back to the model
   **framed as untrusted data** (`<tool_result trust="untrusted-data">…`, markup neutralized so the data
   cannot close the frame).
6. At most `ai.maxToolCallsPerTurn` calls; identical repeated calls are refused; the last round offers no
   tools so the model must answer.
7. `done` carries the sanitized answer (no images, no HTML, only `http(s)` or in-portal links, known secret
   values masked), the cited sources, caveats and pending action ids. The turn is stored for its owner.

Streamed events: `delta`, `tool_call`, `tool_result`, `source`, `pending_action`, `error`, `done`.

## Writing a tool

Tools live with the domain that owns the data (media in 024, tickets in 016…). Register them with the SDK:

```python
from portalab.capabilities.ai import AITool, SourceRef, ToolResult, register_ai_tool

async def handler(principal, params):              # principal = AI acting for the user
    items = await my_service.search(params["query"], principal)   # the SAME service as the API
    return ToolResult(
        "ok",
        {"items": [{"title": i.title} for i in items]},
        [SourceRef("thing", f"thing:{i.id}", i.title, "real", i.as_of, f"/things/{i.id}") for i in items],
    )

register_ai_tool(AITool(
    name="things.search",                           # <domain>.<verb>; plugins: <plugin>.<verb>
    description="Search things the user can see.",
    params_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    required_permission="things.read",
    sensitivity="read",                             # read | write | sensitive | ai_forbidden
    handler=handler,
    summarize=lambda p: f"Search things for {p['query']!r}",   # shown on confirmation cards
    owner="module:things",
))
```

Rules:

* wrap the domain service — never query another module's tables; the service applies its own rules
  (for instance Support refuses ticket submission by the assistant: it only prepares drafts);
* return sources for facts (`real` with `as_of`, `historical`, `knowledge`) and a state
  (`ok | partial | stale | unavailable | error`); degraded states become caveats in the answer;
* never return secrets — keys looking like credentials are masked anyway;
* the sensitivity is checked against the permission registry: a permission that requires confirmation
  makes the tool `sensitive`; reserved permissions make it `ai_forbidden` (see
  [ai-sensitive-actions.md](ai-sensitive-actions.md));
* `AIToolRegistry.unregister(owner)` removes every tool of a module or plugin (023 conformance sweep).

Baseline read tools shipped by the AI module: `search.query` (008), `wiki.search` and `help.page` (011),
`services.status` (006), `statistics.list` / `statistics.get` (017), `navigate.suggest` (004).

## Attribution

Sources retrieved during a turn are numbered; the answer may cite `[n]` only for those — any other marker is
removed, so no invented source can be displayed. An answer citing nothing is labelled *interpretation*.

## Providers

`ai.provider.kind = openai_compatible` covers hosted APIs and local servers (Ollama, vLLM, LM Studio…):
Chat Completions with streaming and tool calling over `httpx`. The provider key is a secret setting
(`ai.provider.apiKey`), sent only as a bearer header, never logged or echoed; failures map to stable codes
(`auth`, `rate_limited`, `timeout`, `unreachable`, `http_<n>`, `invalid_response`, `oversized`). Tool names
travel as `domain__verb` (providers reject dots). New adapters implement `LLMProvider` and pass
`LLMProviderContractKit` (`portalab.capabilities.ai.testkit`).

Optional semantic search: set `ai.embeddings.model` and `ai.embeddings.dimension` to register an
OpenAI-compatible `search.embedding` provider for 008.

## Ports for other specs

| Capability | Consumer | Policy |
|---|---|---|
| `search.assistant` | 008 search assist / palette | read tools `wiki.search`, `services.status`; sources only among permitted refs |
| `support.diagnosis_executor` | 016 diagnosis | no tools; returns an analysis labelled as interpretation, never a ticket |
| `ai.invoke` | 019 automations | read tools only, capped plain text; never a condition nor sensitive input |
| `search.embedding` | 008 semantic search | only when configured |

They are registered **only while the assistant is available**; when it is turned off they are withdrawn and
consumers fall back to their classic path.

## MCP servers (e.g. MCParr)

`ai.mcp.servers` lists servers (`name`, `url`, `allowlist[{tool, permission, sensitivity}]`); credentials
are in the secret setting `ai.mcp.tokens` (`{server: token}`). Only allow-listed tools that the server
actually lists are offered, named `mcp.<server>.<tool>`; the portal authorizes the mapped permission before
every call; `sensitive` (the default) requires confirmation. A server that is down contributes no tools.
Admin UI: *Administration → Assistant settings*.

Deviation from the plan: the client speaks the MCP *Streamable HTTP* transport (JSON-RPC
`initialize` / `tools/list` / `tools/call`, JSON or SSE answers) directly with `httpx` instead of the `mcp`
SDK, so no new dependency is needed.

## Privacy, limits and observability

* Conversations are owner-only (an Admin gets 404), deletable by the user, purged after `ai.retentionDays`,
  exported to and erased with their owner; raw tool results are never stored.
* Governor: kill switch `ai.enabled`, `ai.rateLimitPerMinute`, `ai.dailyTokenBudgetPerUser` (fail-closed),
  concurrency caps.
* Observability: the `ai` component is fed by `report_ai_call` (provider, model, latency, outcome, tool
  names); module metrics count tool outcomes, pending-action funnel and guard trips — never content.
* Events (`ai.conversation_started`, `ai.action_confirmed|declined|expired`) carry ids only; audit carries
  tool names, ids and parameter hashes — never prompts or answers.

## Admin API (`ai.manage`, audited, never usable by the assistant)

`GET/PUT /api/v1/admin/ai/config` (secrets write-only), `POST /api/v1/admin/ai/provider/test`,
`GET /api/v1/admin/ai/usage` (daily aggregates), `GET/PUT /api/v1/admin/ai/mcp-servers`.

## Recorded deviations (T037)

* MCP client built on `httpx` (no `mcp` SDK dependency) — see above.
* No `ai.diagnosis_executions` table: the diagnosis executor is stateless; Support (016) already stores each
  diagnosis run with its steps and outcome.
* Confirmation relies on the user's session (CSRF) plus the single-use `ConfirmationService` token; no extra
  step-up prompt is asked for AI actions (none of the current permissions requires step-up).
* Embedding provider settings `ai.embeddings.model` / `ai.embeddings.dimension` added to make the optional
  `EmbeddingProvider` configurable.
