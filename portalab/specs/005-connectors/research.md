# Research — Connectors (spec 005, roadmap step 6a)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Connector SDK** (`Connector` base: `key`, config schema, capabilities provided, `test_connection`, `discover`, `sync`, optional `actions`) — connectors are code packages registered at startup; **services** are DB instances of a connector | Capability decoupling (CD-019); additive services | Config-only generic HTTP connector |
| R2 | **Sync produces normalized `SourceRecord`s** (`source_system`, `external_id`, `kind`, payload, `observed_at`, `removed`) delivered to a **`RecordSink` registered by the consuming module** (e.g. media); connectors never write module tables | Module owns its schema; provenance uniform (CD-026) | Connectors writing directly to module schemas |
| R3 | **Removed-at-source = deactivate, never delete**; a failed or partial sync never removes data; full resync only touches rows whose provenance is that service | CD-014, spec FR-021/023 | Mirror-delete |
| R4 | **One sync run per service at a time** (PostgreSQL advisory lock per service) + job dedup key `(service, window)` | Prevents overlapping runs/duplicate effects | Optimistic overlap |
| R5 | **Circuit breaker per service** (closed → open after N consecutive failures → half-open probe) feeding service state; calls always carry timeouts and bounded retry | Resilience IX; protects the portal from slow services | Unbounded retries |
| R6 | **Credentials encrypted via `core.secrets`**, write-only in API, never in logs; outbound HTTP through a `ConnectorHttpClient` (timeouts, size limits, redirect policy same-host, TLS verify configurable, correlation id) | Security; homelab targets are private IPs so no private-range blocking | Free `httpx` use per connector |
| R7 | **Auto-discovery only against operator-supplied targets**, candidates stored and never auto-enabled | OQ-24 default, FR-005 | Network scanning |
| R8 | **Compatibility manifest** (portal version range, required capabilities/permissions) checked at enable/update (hook used by 020 toggle service) | FR-029 | Runtime failure discovery |
| R9 | **Capability resolution = registry from 001**: enabling provides, disabling/disconnecting withdraws; multiple providers ordered by admin priority | OQ-20 default | Consumer picks a service |
| R10 | **Concrete connectors (Plex, Radarr, …) are out of this spec's plan**: this plan ships the SDK, runner, conformance kit and a `fake` connector; each real connector is planned with its domain (Media 024 etc.) | Scope control | Implementing providers now |

No `NEEDS CLARIFICATION` remains; OQ-20..24 use registry defaults.
