# Data Model — Search (schema `search`)

## search.history (personal data, class `activity`)
`id` · `user_id` FK `identity.users(id)` · `query_text` · `mode` (`exact|semantic|mixed`) · `filters` jsonb · `performed_at` · unique per `(user_id, normalized_query)` upsert bumping `performed_at`/`count`. Private to the owner (no cross-user read path exists); capped by retention (default 90 days / last 50); erased/exported by the 020/021 participants; disabled per user via `search.historyEnabled`.

## search.embeddings (derived, rebuildable) — requires pgvector
`kind` · `id` (opaque ref to the owner's object, **no FK**) · `language` · `vector` (`vector(N)`) · `content_hash` · `visibility_epoch` · `indexed_at` · PK `(kind, id, language)`. Contains no text. Rebuild = replay of provider `Indexable` documents. Drop-safe: removing the table degrades semantic mode only.

## search.index_state
`kind` · `last_full_reindex_at` · `pending_count` · `last_error` · `embedding_model` — operational state for admin/observability.

## Declared, not stored here
`SearchProvider` registrations and facet definitions (in-memory capability registry rebuilt at startup) · `ActionCatalog` entries (module/plugin manifests via 004 contribution mechanism, `kind=command` extended with `sensitivity`) · `ObjectResolver` registrations.

## Baseline action catalog (OQ-39 default)
`go:<destination>` (from navigation) · `search:<text>` · `new-ticket` (016) · `toggle-theme`, `set-language` (022/026, own preferences) · `sign-out` · `open:<object ref>`. Sensitive/destructive examples require provider-declared `sensitivity` and a confirmation token: `account.request-deletion` (sensitive), admin actions per owner module.

## Settings (declared into 020)
Global: `search.providerTimeoutMs` (1500), `search.maxResultsPerGroup` (10), `search.maxQueryLength` (256), `search.historyRetentionDays` (90), `search.historyMaxEntries` (50), `search.semantic.enabled` (false until a provider exists), `search.semantic.embeddingProvider`, `search.semantic.topK`. User: `search.historyEnabled`.

## Events (via 007)
Produced: `search.performed` (aggregate counts, no query text), `search.provider_failed` (diagnostic, deduped per minute window). Consumed: provider-domain `*.created|updated|deleted|visibility_changed` only through the provider's own indexing job (no generic wildcard consumer).
Dedup: `(user_id, request_id)` for `search.performed`.
