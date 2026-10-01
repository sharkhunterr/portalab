# Contract — Capability Declaration & Registry

A **Capability** is a functional contract between consumers (modules) and providers (connectors or modules).
Adding a service must be additive: no consumer changes (spec 005 FR-001..004).

## Declaration (in `capabilities/`)

- A capability = **name** (`media.library`, `media.playback`, `request.service`, …) + **Protocol** (typed methods
  and result models) + **metadata**: version, required permissions, supported **functional states**, whether
  multiple providers may coexist.
- Result models carry **provenance** (`source_system`, `external_id`, `observed_at`) and a **freshness** marker so
  consumers can render `stale`/`partial`/`unavailable` (spec 006/024).

## Provision

- A connector/module calls `registry.provide(capability, provider, instance_ref)` at load; the instance is a
  *service* row owned by Connectors (005). Providers expose `health()` (technical) and report sync state
  separately — Services & Health (006) and Observability (025) read both.
- Providers are loaded through a failure-isolating wrapper: exceptions/timeouts become typed
  `Unavailable | Timeout | InvalidResponse | AuthenticationFailed` results, never unhandled crashes.

## Resolution

- `registry.resolve(capability, *, context)` returns the provider(s) the **acting user may use** (permission +
  privacy filtered). Multiple providers: deterministic ordering by admin-configured priority (005 OQ-20 default);
  consumers never name a service.
- No provider ⇒ a typed `NoProvider` result → consumers render `unavailable/no data`, never fail the page.

## Conformance

- Each capability ships a **conformance test kit**; every provider must pass it in CI (with a fake external
  service for latency/timeouts/garbage payloads/auth errors).
- Contracts are semver'd; breaking change ⇒ new major version served in parallel until providers migrate.

## Non-goals

Defining individual capability catalogs (owned by consuming domains), service instance storage (005),
health presentation (006), plugin manifest (023).
