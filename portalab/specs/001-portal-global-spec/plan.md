# Implementation Plan: Portal Architecture & Technical Foundation (spec 001)

**Branch**: `spec/001-architecture` | **Date**: 2026-10-01 | **Spec**: `specs/001-portal-global-spec/spec.md`
**Roadmap position**: Phase 1 — SOCLE, step 1 *Architecture* (and the conventions of step 2 *Data*).
**Scope**: the portal-wide technical architecture and foundation that every other spec plans against. It does
**not** plan other specs in detail and contains **no code and no tasks**.

**Sources of truth (priority)**: Constitution v1.0.0 → `decisions/CANONICAL_DECISIONS.md` → Blueprint →
`decisions/TRACEABILITY_MATRIX.md` → spec 001 → other specs (boundaries only) → repository (no code yet).

## Summary

A **modular monolith**: a Python 3.12 / FastAPI backend organised as modules that talk only through
**capability contracts** and **Domain Events**, backed by **PostgreSQL**, serving a **React/TypeScript SPA**,
shipped as one Docker image (+ `postgres`) for self-hosted deployment, built and tested by **GitLab CI**.
Boundaries from the canonical ownership map are **enforced mechanically** (import contracts, schema-per-module)
so "modules depend on capabilities, not services" and "no second engine" are build failures, not conventions.
Research (`research.md`) resolves every technical unknown; stack choices are grounded in the owner's existing
projects (MCParr, pressarr, wrapparr).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain)
**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, Alembic, httpx; React 19, Vite 7,
Tailwind (token-driven), TanStack Query, generated OpenAPI client
**Storage**: PostgreSQL 16+ only (R2); append-only tables for ledger/events/audit (DB-enforced)
**Testing**: pytest + pytest-asyncio against a real PostgreSQL service; Vitest + Testing Library; axe-core; Playwright (few journeys)
**Quality gates**: ruff (lint+format), mypy, import-linter, Biome, `tsc --noEmit`
**Target Platform**: self-hosted Linux containers (Docker/compose), single node
**Project Type**: web application (backend + frontend) with a plugin/connector extension model
**Performance Goals**: interactive responsiveness for a personal/community portal; no fixed numeric SLO
(thresholds are configurable policy — Observability OQ-120); per-widget independent loading is a hard behavior
**Constraints**: offline-capable (no mandatory external runtime service); every failure isolated (principle IX);
all authorization server-side, default-deny; no secrets in code/logs/Git
**Scale/Scope**: personal/community scale (tens–thousands of users); 26 specs, 10 modules, extensible connectors/plugins

Unknowns: **none open** — see `research.md` (R1–R14). Deferred *by design* to the owning specs' plans:
authentication mechanism (002/003), event envelope & dedup key (007), plugin packaging/isolation (023), theming
tokens (022), i18n libraries (026).

## Constitution Check

*Gate before research; re-checked after design — **PASS**, no violations, Complexity Tracking empty.*

- [x] I Product Integrity — plan adds mechanisms only; no business rule touched.
- [x] II Modular Architecture — modules↔capabilities; enforced by import contracts (§3).
- [x] III Extensibility First — extension points reserved; core never imports plugins (§3, §10).
- [x] IV Event-Driven Domain — outbox transport; event model/dedup stay owned by 007 (§6).
- [x] V Source of Truth — provenance columns, no destructive sync/disconnect (§5).
- [x] VI Security — default-deny server-side authz; encrypted credentials; no secrets in logs (§8).
- [x] VII Privacy — tombstone anonymization; PII classification registry (§5).
- [x] VIII Testability — real-DB integration tests, contract tests, CI gates (§9).
- [x] IX Resilience — worker isolation, per-widget loading, timeouts/retry policy (§7).
- [x] X UX Consistency — single SPA shell + design tokens (§4).
- [x] XI Functional State vs Presentation — tokens swap appearance only (§4).
- [x] XII Accessibility — WCAG 2.2 AA gates in CI (§9).
- [x] XIII Observability & Auditability — structured logs + correlation ids; audit owned by 007+003 (§7).
- [x] XIV Deterministic Rules / XV Economy — integer amounts, append-only ledgers (§5).
- [x] XVI/XVII AI & Search independence — separate async paths, SSE streaming (§4).
- [x] XVIII Configuration Hierarchy — bootstrap vs Administration config boundary (§8).
- [x] XIX Versioning — expand/contract migrations, versioned APIs (§5, §11).
- [x] XX Simplicity — no broker, no cache, no microservices, one DB, one image (§12).

## 1. Architecture

```
                     ┌──────────────────────── Browser ────────────────────────┐
                     │ React SPA: shell · design tokens · generated API client  │
                     └───────────────┬───────────────────────▲──────────────────┘
                              REST /api/v1 (JSON, problem+json)   SSE (live updates)
┌─────────────────────────────────────▼───────────────────────┴──────────────────┐
│ portalab (one image: `serve` and `worker` entrypoints)                           │
│  app ── HTTP routing, auth middleware, correlation ids, OpenAPI                   │
│   │                                                                               │
│   ├─ modules/*      home media community statistics support marketplace services  │
│   │                 news-calendar administration … (domain + API + repos)         │
│   ├─ connectors/*   implement capability Protocols for external services          │
│   ├─ plugins (runtime loader — never imported by core)                            │
│   ├─ capabilities/  typed contracts (Protocols) + CapabilityRegistry              │
│   └─ core/          kernel: db, ids, time, errors, jobs/outbox, secrets, logging  │
└───────────────┬───────────────────────────────────────────────┬──────────────────┘
        PostgreSQL (schema per module)                    External services (via connectors)
```

- **Layering (outer→inner imports forbidden)**: `core` ← `capabilities` ← `modules` / `connectors` ← `app`.
- **Capability = contract**: a `Protocol` + metadata declared in `capabilities/`; implemented by connectors or
  modules; resolved at runtime from the **CapabilityRegistry** (so adding a service is additive, spec 005 FR-003).
- **Cross-module communication**: (a) call a capability contract, or (b) publish/consume a Domain Event. Never
  import another module's internals; never join across module schemas.
- **Cross-cutting capabilities** (AI, Search, Events, Automations, Gamification, Statistics, Notifications,
  Permissions/Privacy, Administration/Config, i18n, Accessibility, Observability) are **owned by one module each**
  per the ownership map; this plan only fixes *how* they are wired, not their internals.

## 2. Component Boundaries

| Component | Responsibility | Depends on | Key interface | Constraint | Testing implication |
|---|---|---|---|---|---|
| `core.db` | async engine/session, unit-of-work, schema-per-module, UTC/`timestamptz` enforcement | PostgreSQL | `UnitOfWork`, `Base` per module schema | no cross-module FKs except `identity.users` | integration tests on real PG |
| `core.ids` / `core.time` | UUIDv7 generation; clock abstraction (`now()`), `occurred_at`/`received_at` helpers | — | `new_id()`, `Clock` | clock injectable | deterministic unit tests |
| `core.errors` | error taxonomy → RFC 9457 problems; unavailable/stale/unauthorized states | — | `PortalError` hierarchy | never leak internals/secrets | contract tests on problem shape |
| `core.jobs` | durable jobs + transactional outbox, `SKIP LOCKED` claiming, retry/backoff, timeouts | `core.db` | `enqueue()`, `claim()`, handler registry | at-least-once; handlers idempotent | concurrency + crash-recovery tests |
| `core.secrets` | encrypt/decrypt credentials, redaction | key material | `SecretBox` | write-only in APIs; never logged | secret-scan + redaction tests |
| `core.logging` | structured JSON logs, correlation id propagation, metrics hooks | — | logger factory | no PII/secrets | log-shape tests |
| `capabilities` | contract Protocols + `CapabilityRegistry` (declare/provide/resolve, health of provider) | `core` | `provide()`, `resolve()` | resolution deterministic (005 OQ-20 default: admin priority) | contract-conformance test kit |
| `modules/<name>` | one domain each (see ownership map) | `core`, `capabilities` | its API router + capability/event contracts | owns its schema/migrations | per-module suites + boundary lint |
| `connectors/<name>` | adapt one external service to capability Protocols | `core`, `capabilities` | Protocol impls | timeouts, retries, stale-data semantics | contract-kit + fake external service |
| `app` | composition root: loads modules/connectors/plugins, middleware, routers | all | ASGI app, CLI (`serve`,`worker`,`migrate`) | the only place allowed to import everything | smoke + readiness tests |
| `frontend` | SPA shell, tokens, generated client, per-widget state handling | OpenAPI | typed client, token CSS vars | no business rules; UI never the authz boundary | Vitest + axe + few E2E |

## 3. Boundary Enforcement & Extension Model

- **import-linter contracts** (CI-blocking): layers above; `modules.*` mutually independent; `core` imports no
  `modules/connectors/plugins`; `plugins` import only `capabilities` + published module SDKs.
- **Plugins**: discovered by a registry at startup (packaging format & isolation level decided in the
  Extensibility plan, spec 023). Architecture guarantees now: core has **no import path** to plugins; plugin
  failures are caught at the loader/handler boundary and reported to Observability; a disabled plugin leaves
  data intact (schema namespace per plugin, migrations on a separate branch).
- **Connector ≠ Service ≠ Module ≠ Plugin** (task-level glossary): *connector* = code implementing capability
  Protocols; *service* = configured instance row (`connectors` schema, owned by 005); *module* = first-party
  domain; *plugin* = optional third-party/extension package.

## 4. Frontend Architecture

- Single SPA = the persistent **shell** (spec 004); routes are contributed by modules/plugins from a
  permission-filtered **navigation manifest** served by the API (dynamic nav, spec 004 FR-005/006).
- **Per-widget/section independent loading** via TanStack Query boundaries; every data region renders the
  standardized **functional states** (loading, available, partial, stale, error, unavailable, maintenance,
  unauthorized, no data, syncing) through one shared state component (CD-022/XI).
- **Design tokens** (CSS custom properties) carry colors, type, density, motion; themes replace tokens only.
  `prefers-reduced-motion`, contrast and text-size preferences override token effects (CD-027).
- **Search ∥ AI**: two independent requests; classic results render from the REST response, AI output
  streams over SSE; either failing never blocks the other (CD-017).
- Server is the authorization boundary: the SPA hides what the server refuses but is never trusted.

## 5. Data Conventions (roadmap step "Data")

Full detail in `data-model.md`. Summary:

- **Ids** UUIDv7; **instants** `timestamptz` UTC; occurrence facts carry `occurred_at` + `received_at`;
  `received_at` is never an identity (CD-012). Row bookkeeping: `created_at`, `updated_at`.
- **Schema per module**; FKs only intra-module or to `identity.users(id)`; cross-module references are logical ids.
- **Append-only** tables (events, audit, Coin ledger, purchases) enforced by DB triggers; corrections are new rows.
- **Provenance**: external rows have `source_system`, `external_id` (unique together), `provenance` JSONB;
  disconnecting a service never deletes rows (CD-014).
- **Anonymization = tombstone** of the user row (PII nulled, id preserved) + PII **classification registry** in
  model metadata so export/erasure (Privacy 021) walks columns generically; Coins destroyed by a ledger
  `destruction` entry (CD-005).
- **Migrations**: Alembic, one environment, module-contributed version locations, plugin branch labels;
  forward-only in production using **expand/contract**; every schema change ships with a migration test.

## 6. Events & Background Work

- Transport primitive only: **transactional outbox + durable jobs** in PostgreSQL (`core.jobs`). The **event
  envelope, identity, dedup key and replay semantics are owned by spec 007** and planned there; this plan fixes
  that (a) publishing happens in the same transaction as the state change, (b) delivery is at-least-once,
  (c) every consumer is idempotent and keyed per CD-012, (d) a failing consumer never blocks producers or peers.
- Worker (`portalab worker`) and API share the code base; handlers register through the job registry.
- Live push to the browser uses SSE fed from the same outbox (no separate broker).

## 7. Resilience, Observability, Failure Handling

| Situation | Baseline behavior |
|---|---|
| External service timeout/unavailable | per-connector timeout + bounded retry with jitter; result tagged `stale`/`unavailable`; last-known data served; no deletion (CD-014) |
| Malformed external data | validated at connector boundary (Pydantic); rejected/quarantined with a structured error, never partially applied |
| Plugin/handler exception | caught at boundary; reported; plugin may be auto-disabled by policy; other work continues |
| Duplicate request | `Idempotency-Key` on mutating endpoints; unique constraints on business keys |
| DB unavailable | `/readyz` fails; API returns `503 problem+json`; no partial writes (unit of work) |
| Permission failure | `403`/`404` per existence-leak policy (OQ-19 default); audited when sensitive |
| Observability sink down | logging/metrics fail open — never blocks a request (spec 025 FR-032) |

- **Logs**: structured JSON, correlation id on every request/job/event, secret redaction filter. **Metrics**:
  counters/histograms exposed in Prometheus format for the Observability module (025) to consume; product-level
  health/anomaly logic stays in 025.

## 8. Security, Privacy, Configuration

- **AuthN/AuthZ**: mechanism planned in the *Auth/Permissions* step (002+003); invariant fixed here: every route
  is deny-by-default through a mandatory dependency, authorization is evaluated server-side, AI/automations/
  plugins call the same `authorize()` with the *acting user's* context (CD-003).
- **Secrets**: only bootstrap secrets from env/`*_FILE`; credentials in DB are encrypted (`core.secrets`);
  never in logs, errors, audit payloads or API responses.
- **Configuration boundary (CD-011)**: bootstrap env = `DATABASE_URL`, `SECRET_KEY_FILE`, bind/log level only.
  All product settings are *declared* to Administration (020): `declare_setting(scope, key, schema, default)`;
  no module owns a config store. i18n/Observability/etc. keys (e.g. `i18n.defaultLanguage`) register this way.
- **Privacy**: visibility engine is owned by 021; the kernel supplies the PII classification registry and the
  tombstone convention so every module is erasure/export-compatible by construction.

## 9. Testing Strategy (portal-wide)

- **Unit**: pure domain logic (rules, state machines, resolution algorithms) — fast, no I/O.
- **Integration**: real PostgreSQL service in CI; migrations applied from scratch **and** upgraded from the
  previous release; outbox/claim concurrency and crash-recovery tests.
- **Contract**: capability-conformance kits (any connector must pass), OpenAPI snapshot diff to catch breaking
  API changes, problem+json shape.
- **Boundary**: import-linter + "no cross-schema FK" test.
- **Security/permission**: deny-by-default test per router (generated from the route table), tenant-free
  but role/permission matrix tests; secret-scan on logs/fixtures.
- **Events/idempotence**: duplicate-delivery tests for every consumer (CD-012).
- **UI**: Vitest (states: loading/empty/error/unauthorized), axe (WCAG 2.2 AA), a handful of Playwright journeys.
- **Resilience**: fake external service with latency/timeouts/garbage; degraded-mode tests.
- Test depth is **proportional to risk** (sensitive: auth, permissions, ledger, purchases, deletion, audit).

## 10. CI/CD (GitLab) — design only

Follows the sibling pipelines' stage names and templates (`python:3.12-slim`, `node:22-alpine`, docker-in-docker):

| Stage | Jobs |
|---|---|
| `validate` | ruff, mypy, import-linter, Biome, `tsc --noEmit`, OpenAPI client drift check, secret scan |
| `test` | backend unit+integration (PostgreSQL service), migrations from-scratch + upgrade, frontend Vitest/axe, Playwright (default branch + MR label) |
| `build` | multi-stage Docker image (frontend built, served by backend) |
| `publish` | on tags: registry push + release notes (kept optional like siblings: `ENABLE_*` variables) |

Pipelines run on merge requests, the default branch and tags (not tags-only). Caches keyed by lockfile.
No manual steps; no dependency on a developer machine.

## 11. Versioning & Migration

- API: `/api/v1`; additive changes within a version; breaking change ⇒ new version with overlap.
- DB: expand/contract; destructive steps only in a later release and never on ledger/event/audit tables.
- Extension contracts (capability Protocols, plugin manifest) are semver'd; compatibility checked on enable (023).
- Config keys carry a schema version so admin policy/preferences migrate without silent reset.

## 12. Technical Decisions & Trade-offs

| Decision | Why | Cost / rejected alternative |
|---|---|---|
| Python/FastAPI + React/TS | matches owner ecosystem, MCParr, CI | two languages (vs TS-only; rejected for ecosystem fit) |
| PostgreSQL only | ledger/outbox/dedup need real concurrency & features | extra container (vs SQLite) |
| Modular monolith + import contracts | canonical ownership enforced, ops-simple | discipline needed; split later is possible |
| Outbox in PostgreSQL, no broker | atomic publish, zero extra infra | throughput ceiling (acceptable at personal scale; revisit if needed) |
| SSE not WebSockets | one-way, simple, resilient | no client→server stream (not needed) |
| UUIDv7 | locality + non-guessable | dependency on a UUIDv7 library on Python 3.12 |
| Tombstone anonymization | keeps FK/ledger integrity | consumers must handle tombstoned users |

## 13. Roadmap Sequencing (what this plan hands to the next steps)

Each next step runs its own `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` on branch `spec/<NNN>-<name>`.

| Roadmap step | Spec(s) | Needs from this plan | Contracts it must expose |
|---|---|---|---|
| **P1.1 Architecture** | 001 | — (this plan) | repo layout, kernel, registry, CI skeleton |
| **P1.2 Data** | 001 (kernel) + 021 conventions | §5, `data-model.md` | `core.db`, ids/time, jobs/outbox, migrations harness, PII registry |
| **P1.3 Auth / Permissions** | 002, 003 | kernel, error model | `authorize()`, identity (`users`), roles/permissions, session; **audit sink port** (store lands with 007 — see risk R-A) |
| **P1.4 Configuration** | 020 (config part) | kernel, authz | `declare_setting()`, hierarchy resolver, admin API |
| P2.1 Events/History | 007 | outbox, ids/time | event envelope, dedup, history, audit store |
| P2.2 Connectors/Services | 005, 006 | registry, secrets, jobs | capability contracts, service instances, sync |
| P2.3 Observability | 025 | logging/metrics hooks | health model, errors, anomalies |
| P3 UX | 022, 004, 026, 008 | SPA scaffold, tokens | design system, shell, i18n runtime, search |
| P4…P8 | 009,006,017,010 / 024,016,018 / 013,014,019 / 012 / 015,023 | prior phases | per spec |

**Implementation work packages of *this* plan** (turned into tasks later): WP1 repo scaffold + tooling + CI
skeleton; WP2 kernel (`db`, `ids`, `time`, `errors`, `logging`, `secrets`); WP3 job/outbox primitive; WP4
capability registry + module loader + boundary lint; WP5 frontend scaffold (shell stub, tokens, generated
client); WP6 container image + compose + `migrate/serve/worker` CLI; WP7 conventions test-kit.
Independent: WP1 first; WP2–WP4 sequential on kernel; WP5 parallel after WP1; WP6 after WP2; WP7 after WP2–WP4.

## 14. Risks / Open Technical Questions

- **R-A (sequencing)**: audit storage is owned by 007+003 (CD-013) yet Auth (Phase 1) must audit sensitive
  actions before Events (Phase 2). *Mitigation*: Auth plan defines an `AuditSink` port; Phase 1 ships a minimal
  append-only `audit` table behind it that 007 later adopts/migrates — **no second audit model** (flagged to
  confirm in the 002/003 plan).
- **R-B**: UUIDv7 on Python 3.12 needs a small library (stdlib adds it in 3.14) — pin and wrap in `core.ids`.
- **R-C**: PostgreSQL-only excludes SQLite-style zero-ops installs — documented in quickstart; revisit only if
  adoption demands.
- **R-D**: in-process plugins share the process; true isolation level is a Phase 8 decision (023) — until then
  plugins are trusted-admin-installed (OQ-111 default).
- **R-E**: plan 026 assumes TS end-to-end (see `research.md` R12) — re-validate at Phase 3.
- **R-F**: repo is not yet on a remote/GitLab; CI is designed against the sibling conventions and verified when
  the project is pushed (no push performed here).

## Project Structure

### Documentation (this feature)

```text
specs/001-portal-global-spec/
├── spec.md · plan.md (this file) · research.md · data-model.md · quickstart.md
├── contracts/ (module-boundaries.md · capability-contract.md · api-conventions.md · bootstrap-settings.md)
└── checklists/requirements.md          # tasks.md is produced later by /speckit.tasks
```

### Source code (repository root `portalab/`) — target layout, created during implementation

```text
backend/
├── pyproject.toml · uv.lock · importlinter.ini
├── src/portalab/
│   ├── core/            # db, ids, time, errors, jobs, secrets, logging, settings (bootstrap only)
│   ├── capabilities/    # contract Protocols + CapabilityRegistry
│   ├── modules/         # one package per domain module (own schema + migrations dir)
│   ├── connectors/      # one package per external service adapter
│   ├── app/             # composition root, middleware, CLI (serve · worker · migrate)
│   └── plugins_runtime/ # loader/registry (no plugin code in core)
├── migrations/          # Alembic env + core versions; modules contribute version locations
└── tests/{unit,integration,contract,boundary}/
frontend/
├── package.json · package-lock.json · biome.json · tsconfig.json
├── src/{shell,design-system,features,api(generated),i18n,state}/
└── tests/{unit,a11y,e2e}/
deploy/  Dockerfile · docker-compose.yml · .env.example
.gitlab-ci.yml
```

**Structure decision**: web application (backend + frontend) monorepo next to the existing documentation
packages (`product/`, `architecture/`, `specs/`, `decisions/`), which remain untouched.

## Complexity Tracking

No Constitution violations — nothing to justify.

## Post-design Constitution re-check

After `data-model.md` and `contracts/`: **PASS** — conventions add no product rule, no second
config/rules/event/audit/monitoring engine, and keep one owner per responsibility.
