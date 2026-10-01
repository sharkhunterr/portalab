# Contract — HTTP API Conventions

Applies to every module/plugin router. Individual endpoints are defined in each spec's plan.

| Topic | Convention |
|---|---|
| Base & versioning | `/api/v1/...`; additive changes inside a version; breaking change ⇒ `/api/v2` served in parallel |
| Contract | OpenAPI generated from the backend; the frontend client is **generated** and CI fails on drift |
| Format | JSON; field names `snake_case`; instants ISO-8601 UTC (`...Z`); ids as UUID strings |
| Errors | RFC 9457 `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`, plus `code` and `correlation_id`; never internals/secrets |
| AuthN | session/token mechanism defined by 002/003; **every route requires an explicit authorization dependency** (default-deny); public exceptions (sign-in, health) are allow-listed |
| AuthZ failures | `401` unauthenticated; `403` forbidden; `404` when revealing existence is itself sensitive (existence-leak default, OQ-19) |
| Idempotency | all mutating endpoints that spend, award, purchase, create tickets, or trigger syncs accept `Idempotency-Key`; replay returns the original result; business keys are also unique in the DB |
| Pagination | cursor-based (`limit`, `cursor`); response `{items, next_cursor}`; stable ordering by `(occurred_at, id)` |
| Filtering/sorting | explicit allow-listed query params per endpoint; unknown params ⇒ `400` |
| Functional states | list/detail responses may return `state: available|partial|stale|unavailable|syncing…` + `as_of` for freshness; unavailable sources never turn a whole response into `5xx` |
| Concurrency | `ETag`/`If-Match` on editable resources (wiki, config) to prevent lost updates |
| Live updates | `GET /api/v1/stream` (SSE), permission-filtered; events are *notifications to refetch or small deltas*, never the source of truth |
| Health | `/healthz` (process alive), `/readyz` (DB reachable + migrations current); both unauthenticated, no sensitive detail |
| Correlation | `X-Correlation-Id` accepted/generated, echoed in responses, logs and jobs |
| Rate/size limits | request size caps; per-user rate limits configurable via Administration |
| i18n | `Accept-Language` is only a hint; the resolved `LocaleContext` (026) governs; error `title/detail` localized, `code` stable |
