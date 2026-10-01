# Research — Architecture & Technical Baseline (spec 001)

**Date**: 2026-10-01 · **Scope**: resolves every `NEEDS CLARIFICATION` of the architecture plan
(`plan.md`). Decisions here are the **portal-wide technical baseline** that the project owner delegated to
this plan ("décider dans le plan de la 1re spec"). They never override product decisions (Constitution,
CANONICAL_DECISIONS.md, Blueprint, specs).

## Evidence: confirmed repository / ecosystem constraints

| Fact | Source | Consequence |
|---|---|---|
| `portalab` holds **no implementation code**; docs and specs only | repo inspection | Nothing to preserve or migrate |
| Owner's sibling projects share one stack: Python 3.11–3.12 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic 2 + httpx; React + TypeScript 5.x + Vite + Tailwind + i18next; Docker; GitLab CI | `mcparr`, `pressarr`, `wrapparr` (read-only inspection) | Reuse skills, CI conventions and libraries; lowest maintenance cost for a single maintainer |
| **MCParr** (FastAPI gateway) is an optional access/action layer the AI may use (CD-021) | `mcparr/README.md` | Python/HTTP integration is natural; MCParr must stay *optional* |
| Existing GitLab pipelines use stages `validate → test → build → publish`, `python:3.12-slim`, `node` images, Docker-in-Docker | `pressarr/.gitlab-ci.yml` | New CI follows the same stage names/templates; does not invent a different shape |
| Self-hosted homelab deployment (Docker/compose) | Blueprint "personal portal", sibling projects | Single-node target; operator simplicity is a hard requirement |
| Node 22 / npm 10 available locally; npm registry reachable | environment check | Frontend toolchain can be pinned to Node 22 LTS |

## Decisions

### R1 — Backend language & framework
- **Decision**: **Python 3.12 + FastAPI + Pydantic 2**, async I/O, typed end-to-end (`mypy`), `ruff` for lint/format.
- **Rationale**: matches every sibling project and MCParr; Pydantic gives validated contracts (spec "Validation"); FastAPI emits OpenAPI used to generate the TypeScript client; async fits many slow external services (Connectors, resilience principle IX).
- **Alternatives**: TypeScript/NestJS (single language with the SPA, but diverges from the owner's ecosystem and CI know-how); Go (fast, but no reuse and heavier plugin story). **Supersedes** the "TS end-to-end" proposal in `specs/026-i18n/plan.md` §1/§16 (see R12).

### R2 — Database
- **Decision**: **PostgreSQL 16+ as the only supported database** (no SQLite mode). `asyncpg` driver, SQLAlchemy 2.0 async ORM, Alembic migrations.
- **Rationale**: the product needs transactions + concurrency for an append-only Coin ledger, an event store with deduplication (CD-012), `SELECT … FOR UPDATE SKIP LOCKED` job claiming, partial/unique indexes for idempotency, JSONB for provenance/metadata, and `timestamptz`. A SQLite/PostgreSQL dual mode would double the test matrix and forbid those features.
- **Alternatives**: SQLite (sibling projects use it; simpler single-file ops but weak concurrency, no SKIP LOCKED, awkward ledger/outbox guarantees); MariaDB (viable, but loses JSONB/partial indexes). Trade-off accepted: one extra container (`postgres`) in compose.

### R3 — Architectural style
- **Decision**: **Modular monolith**: one deployable backend, modules as internal packages with explicit boundaries, communicating only through **capability contracts** (typed `Protocol`s resolved from a registry) and **Domain Events**. Optional second process = the same image started as `worker`.
- **Rationale**: respects "Portal → Modules/Plugins/Connectors/Services/Capabilities" without microservice operations cost; boundaries are enforced mechanically (R9) so a future split stays possible.
- **Alternatives**: microservices (rejected: operations burden for a self-hosted personal portal; violates principle XX simplicity); unstructured monolith (rejected: cannot guarantee "Module depends on capabilities, not services").

### R4 — Frontend
- **Decision**: **React 19 + TypeScript 5.9 + Vite 7 SPA**, Tailwind CSS driven by **design tokens as CSS custom properties** (themes swap tokens, never functional state — CD-022), TanStack Query for server state, typed client **generated from the OpenAPI schema**. Tests: Vitest + Testing Library; a11y: `axe-core` in component/E2E tests; E2E: Playwright (few critical journeys).
- **Rationale**: same toolchain as MCParr/pressarr; SPA fits the persistent shell (spec 004); token-based theming + WCAG 2.2 AA floor (CD-027).
- **Alternatives**: Next.js/SSR (rejected: no SEO need, authenticated-only portal CD-025, adds a Node runtime); server-rendered templates (rejected: extensible widget/plugin UI and rich shell need a client runtime).

### R5 — API style, live updates, errors
- **Decision**: **REST/JSON, versioned under `/api/v1`, OpenAPI as the contract**; **Server-Sent Events** for live updates (notifications, playback, health) instead of WebSockets; errors as **RFC 9457 `application/problem+json`**; **cursor pagination**; mutating endpoints accept an **`Idempotency-Key`** header (duplicate purchases/awards must be impossible, CD-012).
- **Rationale**: simplest transport that satisfies "classic search shows immediately while AI streams in parallel" and per-widget independent loading; SSE is one-directional, proxy-friendly, auto-reconnecting.
- **Alternatives**: GraphQL (rejected: more machinery, caching/permission complexity); WebSockets (kept only where bidirectional need appears, none today).

### R6 — Background processing & events transport
- **Decision**: **PostgreSQL-backed jobs + transactional outbox**, claimed with `FOR UPDATE SKIP LOCKED`, run by an in-process scheduler/worker (APScheduler-style timing, durable state in DB). **No Redis/Celery/broker in the baseline.**
- **Rationale**: events, sync, automations, notification delivery all need at-least-once delivery with idempotent consumers (CD-012). An outbox in the same DB gives atomic "write + publish" with zero extra infrastructure. The *event model, identity and dedup rules remain owned by spec 007*; this plan only provides the durable transport primitive.
- **Alternatives**: Redis + Celery (siblings use it optionally; rejected: extra service, dual-write consistency problem); Kafka/NATS (rejected: disproportionate).

### R7 — Time, identifiers, money
- **Decision**: all instants are `timestamptz` stored as UTC; occurrence facts carry **`occurred_at` and `received_at`** (CD-012). Primary keys are **UUIDv7** (time-ordered, generated in the application). Coins/XP/Contribution amounts are **integers** (no floats) with ledgers append-only (enforced by DB triggers, detailed in spec 013's plan).
- **Rationale**: absolute-instant storage is the prerequisite for DST-correct i18n (spec 026) and deterministic replay; UUIDv7 keeps index locality and avoids guessable ids.
- **Alternatives**: bigserial ids (leak volume, hard to merge instances); UUIDv4 (poor index locality).

### R8 — Provenance, deletion and anonymization conventions
- **Decision**: rows that originate externally carry `source_system`, `external_id` (unique together) and a `provenance` JSONB; rows referencing people reference **`identity.users(id)`** only. **Final deletion = tombstone, not row removal**: PII columns are nulled/replaced, the `id` survives, so ledger/history foreign keys stay valid and integrity-preserving anonymization needs no history rewrite (CD-005/016). Personal-data columns are **tagged in model metadata** (classification registry) so Privacy's erasure/export walks them instead of hard-coding table names.
- **Rationale**: satisfies "historized ≠ public", "transaction integrity preserved", "Coins destroyed" without per-module custom deletion code.
- **Alternatives**: hard delete + orphan FKs (breaks ledger integrity); separate pseudonym tables everywhere (more joins, no extra guarantee).

### R9 — Boundary enforcement
- **Decision**: **`import-linter` contracts in CI** (layers: `core` ← `capabilities` ← `modules`/`connectors` ← `app`; modules may not import other modules' internals; core may not import plugins; connectors implement capability protocols only). Schema-per-module in PostgreSQL; **foreign keys only within a module or to `identity.users`**.
- **Rationale**: turns the canonical ownership map into a failing build instead of a convention.

### R10 — Configuration vs bootstrap settings (CD-011)
- **Decision**: only **bootstrap settings** (database URL, secret/key material paths, bind address, log level) come from environment/files (`*_FILE` secrets). **Every runtime/product setting is declared into the Administration configuration system** (spec 020) along Global → Module → Plugin → User. The kernel exposes a *declaration* API but contains no second config store.
- **Rationale**: avoids the competing-configuration-engine failure the audit flagged.

### R11 — Secrets & credentials at rest
- **Decision**: connector/service credentials are stored **encrypted with an application key** (envelope: key from env/`_FILE`, per-record nonce), exposed only as write-only fields in the API, redacted from logs/errors/audit (Privacy FR-031, Observability FR-031).
- **Alternatives**: plaintext in DB (rejected); external vault (optional future, not a baseline dependency).

### R12 — Impact on already-written artifacts
- `specs/026-i18n/plan.md` (§1, §16) assumed **TypeScript end-to-end + Node Intl**; with a **Python backend** server-side formatting/ICU must use Python CLDR tooling (e.g. Babel) while the SPA uses `Intl` + an ICU message layer. **Action**: re-validate plan/tasks 026 at Phase 3 (they are on branch `spec/026-i18n`, preserved; the TS draft sits in `git stash`). Contract-level design (LocaleContext, fallback chain, config keys) remains valid.
- Product specs, CD-001…CD-027 and the traceability matrix are **unchanged**.

### R13 — Tooling & CI conventions
- **Decision**: backend `uv` (lock + venv) *or* `pip-tools`; choice = **`uv`** for speed/determinism with a committed lock; `pytest` + `pytest-asyncio` + PostgreSQL service container in CI (never SQLite stand-ins); `ruff` (lint+format), `mypy`, `import-linter`; frontend `pnpm`-free: **npm + lockfile**, Biome (lint+format), `tsc --noEmit`, Vitest, Playwright. GitLab stages `validate → test → build → publish` as in sibling projects; pipelines run on merge requests and the default branch (not tags-only), release publishing on tags.
- **Alternatives**: Poetry (used by MCParr; slower, no advantage here); pnpm/yarn (no benefit).

### R14 — Deployment
- **Decision**: **one multi-stage Docker image** (frontend built then served as static files by the backend) + `postgres` in `docker-compose`; the image runs `portalab serve` or `portalab worker`; health endpoints `/healthz` (liveness) and `/readyz` (DB + migrations). Migrations run explicitly (`portalab migrate`) before start, never implicitly on request path.
- **Rationale**: matches the siblings' Docker-first distribution; keeps a single artefact to version and publish.

## Resolved clarifications (none remain open)

Stack, database, style, frontend, API, async/events transport, identifiers/time, deletion/anonymization pattern,
boundary enforcement, config/secret boundaries, CI and deployment are all decided above. Items intentionally
deferred to **later specs' plans** (not unknowns of this plan): authentication mechanism (002/003),
event envelope & dedup key form (007), plugin packaging/isolation (023), theming token catalog (022),
exact i18n libraries (026).
