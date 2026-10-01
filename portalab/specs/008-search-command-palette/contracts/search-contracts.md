# Contracts — Search & Command Palette

## Python capability `capabilities/search`
- `SearchProvider` (Protocol): `kind: str` · `label_key` · `required_permission` · `facets() -> list[FacetDef]` · `async search(query: ParsedQuery, principal, ctx: LocaleContext, *, limit, cursor) -> ProviderResult{items[SearchItem], state: ok|partial|unavailable, took_ms}` · `async hydrate(ids, principal) -> list[SearchItem]` (re-authorizes) · optional `Indexable.documents(since) -> Iterable[IndexDocument{id, language, text, content_hash}]`.
- `SearchItem{kind, id, title, snippet(escaped, with highlight spans), url_ref, language, matched_by: exact|semantic, score, facets}`.
- `EmbeddingProvider` (optional): `embed(texts, language) -> list[vector]`, `dimension`, `model_id`.
- `SearchAssistant` (implemented by 018): `stream(query, principal, result_refs) -> AsyncIterator[AssistEvent{type: source_ref|synthesis|status|error}]`, `interpret(text, principal, page_context) -> list[IntentSuggestion]`.
- `ActionDef{id, label_key, keywords[lang], permission, sensitivity, route|endpoint, confirmation_required}` contributed through the 004 `NavigationContribution(kind=command)`.
- `ObjectResolver.resolve(ref_text, principal) -> ObjectRef | None` per provider kind.

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| POST `/search` | `search.use` (default grant to authenticated) | body `{q, mode, filters, kinds?, cursor?}` → `{groups[{kind, state, items, next_cursor, facets}], took_ms}`; groups for kinds the user cannot access are **absent** |
| POST `/search/assist` (SSE) | `search.use` + AI permission (018) | independent stream; failure never affects `/search` |
| GET `/search/suggest?q=` | `search.use` | typeahead (prefix/trigram), same scoping |
| GET/DELETE `/me/search-history`, DELETE `/me/search-history/{id}` | `users.self.manage` | owner only |
| GET `/palette/resolve?q=&route=` | authenticated | deterministic intents, object refs, context actions; returns only permitted entries |
| POST `/admin/search/reindex`, GET `/admin/search/status` | `search.manage` (audited) | per kind |
Problem codes: `search.query_too_long`, `search.rate_limited`, `search.invalid_filter`.

## Frontend
`SearchProvider` (004 slot contract) implemented here: `<SearchPage>` (grouped results, filters, per-group states via `FunctionalState`), palette provider plugging into the 004 `CommandRegistry` (`registerProvider(searchProvider)`), `useSearchAssist()` SSE hook with distinct "analysis" styling and source labels.

## Extension point (023)
Plugins register a `SearchProvider`/actions through the plugin host; their results are namespaced `plugin:<id>` and subject to the same permission contract.
