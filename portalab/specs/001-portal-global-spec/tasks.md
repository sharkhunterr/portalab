---
description: "Task list — Portal Architecture & Technical Foundation (spec 001, roadmap Phase 1 steps 1–2)"
---

# Tasks: Portal Architecture & Technical Foundation

**Input**: `specs/001-portal-global-spec/` — plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Branch**: `spec/001-architecture` · **Roadmap**: Phase 1 SOCLE → *Architecture* + *Data* conventions
**Tests**: INCLUDED — plan §9 prescribes the testing strategy (real PostgreSQL, boundary, contract, security,
idempotence). Depth is proportional to risk; no coverage-for-coverage tests.

## Scope note (read first)

Spec 001 is the **global** specification (11 user stories). This task list implements only what the approved
plan covers: the **technical foundation** that makes those stories *buildable*. Each story phase below delivers
the foundation slice that story depends on. Stories whose behaviour belongs to later roadmap steps are **not**
implemented here:

| Story | Handled here | Delivered by |
|---|---|---|
| US1 Unified shell | SPA scaffold, tokens, functional-state component, per-region loading | Phase 3 UX (004/022) builds the real shell |
| US2 Capability integration + degradation | **Registry, isolation wrapper, conformance kit** | Phase 2 Connectors (005/006) |
| US3 Event/history loop | **Durable jobs + outbox primitive** | Phase 2 Events (007) |
| US4 Search ∥ AI | **SSE transport + independent-region pattern** | Phase 3 (008) / Phase 5 (018) |
| US5 Onboarding | — | Phase 1 Auth/Config + Phase 3 |
| US6 Economy/Marketplace/community | append-only/ledger DB primitive only | Phase 6–8 |
| US7 Support | — | Phase 5 (016) |
| US8 Privacy/export/deletion | **PII registry, tombstone helper, append-only guard** | Phase 1 Auth (002) / 021 |
| US9 Administration | **Bootstrap settings, secrets, `declare_setting` contract** | Phase 1 Configuration (020) |
| US10 Personalization/themes | tokens only | Phase 3 (022) |
| US11 Automations | — | Phase 6 (019) |

**Conventions**: `[P]` = parallelizable (different files, no incomplete dependency) · `[USn]` = story served ·
paths are relative to the repo root `portalab/`. Commit trailer for implementation commits:
`Co-Authored-By: Claude Code (Anthropic)` (project owner instruction).

---

## Phase 1: Setup (shared infrastructure — plan WP1)

- [X] T001 Create the target directory skeleton from plan "Project Structure": `backend/src/portalab/{core,capabilities,modules,connectors,app,plugins_runtime}/__init__.py`, `backend/migrations/`, `backend/tests/{unit,integration,contract,boundary}/`, `frontend/src/{shell,design-system,features,api,i18n,state}/`, `frontend/tests/{unit,a11y,e2e}/`, `deploy/`
- [X] T002 Create `backend/pyproject.toml` (uv-managed, Python 3.12) pinning FastAPI, Pydantic 2, SQLAlchemy 2 + asyncpg, Alembic, httpx, a UUIDv7 library; dev group pytest, pytest-asyncio, ruff, mypy, import-linter; configure ruff, mypy (strict for `core`/`capabilities`), pytest (asyncio mode, markers `unit|integration|contract|boundary`); commit `backend/uv.lock`
- [X] T003 [P] Create `frontend/package.json` + `package-lock.json` (React 19, TypeScript 5.9, Vite 7, Tailwind, TanStack Query, Vitest, Testing Library, axe-core, Playwright, Biome, openapi client generator), `frontend/tsconfig.json`, `frontend/biome.json`, `frontend/vite.config.ts`, scripts `dev|build|lint|typecheck|test|gen:api`
- [X] T004 [P] Create `backend/importlinter.ini` declaring the layered contract `core ← capabilities ← modules|connectors ← app`, independence of `modules.*`, and "core never imports plugins" per `contracts/module-boundaries.md`
- [X] T005 [P] Create `deploy/.env.example` (bootstrap settings only per `contracts/bootstrap-settings.md`, no real values) and extend root `.gitignore` for `.venv/`, `node_modules/`, `.env`, build output
- [X] T006 [P] Create `.gitlab-ci.yml` with stages `validate|test|build|publish` and the `validate` jobs (ruff, mypy, import-linter, Biome, `tsc --noEmit`, secret scan) using `python:3.12-slim` / `node:22-alpine` templates; MR + default-branch + tag rules

**Checkpoint**: tooling runs (`ruff`, `mypy`, `lint-imports`, `biome`, `tsc`) on the empty skeleton.

---

## Phase 2: Foundational (blocking kernel — plan WP2)

**⚠️ No user-story phase may start before this phase completes.**

### Tests first (fail before implementation)

- [X] T007 [P] Write `backend/tests/unit/test_ids_time.py`: UUIDv7 ids are time-ordered and unique; `Clock` is injectable; `occurred_at`/`received_at` helper rejects naive datetimes (R7)
- [X] T008 [P] Write `backend/tests/unit/test_errors.py`: each `PortalError` maps to RFC 9457 problem+json with `code` and `correlation_id`, and never includes internals or secrets (contracts/api-conventions)
- [X] T009 [P] Write `backend/tests/unit/test_logging.py`: JSON log lines carry the correlation id; secret-looking values (tokens, passwords, `*_KEY`) are redacted

### Implementation

- [X] T010 [P] Implement `backend/src/portalab/core/ids.py`: `new_id()` returning UUIDv7 wrapped behind one function (R-B)
- [X] T011 [P] Implement `backend/src/portalab/core/time.py`: `Clock` protocol + `SystemClock`, `utc_now()`, `require_aware()`, `Occurrence(occurred_at, received_at)` value type (CD-012: `received_at` never an identity)
- [X] T012 [P] Implement `backend/src/portalab/core/errors.py`: `PortalError` hierarchy (`Unauthorized`, `Forbidden`, `NotFound`, `Conflict`, `ValidationFailed`, `Unavailable`, `Timeout`) + problem+json serializer
- [X] T013 [P] Implement `backend/src/portalab/core/logging.py`: structured JSON logger factory, correlation-id context var, redaction filter
- [X] T014 Implement `backend/src/portalab/core/settings.py`: bootstrap settings only (`DATABASE_URL`/`_FILE`, `SECRET_KEY_FILE`, `BIND_HOST`, `BIND_PORT`, `LOG_LEVEL`), fail-fast validation, no business settings (contracts/bootstrap-settings)
- [X] T015 Implement `backend/src/portalab/core/db.py`: async engine/session factory, `UnitOfWork`, per-module schema `Base` factory, `timestamptz`-only type guard
- [X] T016 Create the Alembic environment in `backend/migrations/env.py` + `alembic.ini` supporting module-contributed `version_locations` and plugin branch labels; add the `core` schema revision directory `backend/migrations/versions/`
- [X] T017 Implement `backend/src/portalab/app/main.py`: ASGI app factory, correlation middleware, problem+json exception handlers, default-deny `require_authorization` dependency backed by an `Authorizer` **port** that denies unless a route is allow-listed (mechanism itself comes with Auth/Permissions)
- [X] T018 [P] Implement `backend/src/portalab/app/health.py`: `/healthz` (process) and `/readyz` (DB reachable + migrations current), unauthenticated, no sensitive detail
- [X] T019 Implement `backend/src/portalab/app/cli.py`: entrypoints `serve`, `worker`, `migrate` (explicit migration, never on request path)

### Integration tests for the kernel

- [X] T020 Create `backend/tests/integration/conftest.py`: PostgreSQL fixtures reading a service URL from the environment (CI service container / local compose), per-test schema isolation, **no SQLite fallback**
- [X] T021 [P] Write `backend/tests/integration/test_migrations.py`: upgrade from an empty database succeeds; downgrade is dev-only; `/readyz` flips to ready only after migration
- [X] T022 [P] Write `backend/tests/integration/test_default_deny.py`: every non-allow-listed route in the app's route table returns 401/403 without an authorizer grant (generated from the route table)
- [X] T023 [P] Write `backend/tests/integration/test_health.py`: `/healthz` 200; `/readyz` 503 problem+json when the DB is unreachable

**Checkpoint**: kernel boots, migrates, serves health, denies by default; foundation tests green.

---

## Phase 3: User Story 2 — Capability-based integration with graceful degradation (P1) 🎯 MVP

**Goal**: modules can depend on typed capability contracts resolved at runtime; providers fail in isolation.
**Independent test**: register two fake providers for one capability → consumer works with either; make one
time out/return garbage → consumer receives a typed state, never an unhandled exception; remove all providers → `NoProvider`.
(Plan WP4; spec US2 acceptance 1–3.)

### Tests first

- [X] T024 [P] [US2] Write `backend/tests/contract/test_registry.py`: provide/resolve, deterministic ordering by priority with two providers, `NoProvider` when none, permission-filtered resolution via the `Authorizer` port
- [X] T025 [P] [US2] Write `backend/tests/contract/test_isolation.py`: provider exception/timeout/garbage payload/auth failure become `Unavailable|Timeout|InvalidResponse|AuthenticationFailed` results; bounded retry with jitter; last-known data marked `stale`

### Implementation

- [X] T026 [P] [US2] Implement `backend/src/portalab/capabilities/results.py`: typed result states (`Available`, `Partial`, `Stale`, `Unavailable`, `Timeout`, `InvalidResponse`, `AuthenticationFailed`, `NoProvider`) carrying `provenance` (`source_system`, `external_id`, `observed_at`) and freshness (`as_of`) per `contracts/capability-contract.md`
- [X] T027 [US2] Implement `backend/src/portalab/capabilities/registry.py`: `CapabilityRegistry` (`declare`, `provide`, `resolve`), capability metadata (name, version, required permissions, multi-provider flag)
- [X] T028 [US2] Implement `backend/src/portalab/capabilities/isolation.py`: failure-isolating provider wrapper (timeout, bounded retry, exception→typed result, `health()` separate from sync state)
- [X] T029 [US2] Implement `backend/src/portalab/capabilities/testkit.py`: conformance-kit base class + fake external service (latency, timeouts, garbage, auth errors) reusable by every future connector
- [X] T030 [US2] Add the boundary tests `backend/tests/boundary/test_boundaries.py`: import-linter runs in pytest; no cross-schema foreign key except to `identity.users(id)` (introspects metadata); declared ownership packages exist exactly once (initially skipped-until-present markers documented)

**Checkpoint**: US2 independently verifiable with fakes; Connectors (005) can now implement providers against the kit.

---

## Phase 4: User Story 3 — Product loop transport: durable jobs + outbox (P1)

**Goal**: at-least-once, restart-safe background work and event/notification delivery with idempotent consumers.
**Independent test**: enqueue the same `dedup_key` twice → handler runs once; kill a worker mid-job → another claims
it after the lock expires; failing handler backs off then goes `dead`. (Plan WP3; event *model* stays in spec 007.)

### Tests first

- [X] T031 [P] [US3] Write `backend/tests/integration/test_jobs_dedup.py`: unique `(queue, dedup_key)`; second enqueue is a no-op; no timestamp-only dedup (CD-012)
- [X] T032 [P] [US3] Write `backend/tests/integration/test_jobs_claim.py`: two concurrent workers never claim the same job (`SKIP LOCKED`); expired lock is re-claimed after a crash
- [X] T033 [P] [US3] Write `backend/tests/integration/test_jobs_retry.py`: backoff schedule, `max_attempts` → `dead`, `last_error` is redacted, handler failure never blocks other jobs

### Implementation

- [X] T034 [US3] Implement the `core.job` model in `backend/src/portalab/core/jobs/models.py` and its Alembic revision (fields, status CHECK, partial indexes per `data-model.md` §2)
- [X] T035 [US3] Implement `backend/src/portalab/core/jobs/queue.py`: `enqueue()` (same-transaction outbox use), `claim()` with `FOR UPDATE SKIP LOCKED`, `succeed()`, `fail()` with backoff/`dead`
- [X] T036 [P] [US3] Implement `backend/src/portalab/core/jobs/registry.py`: handler registry keyed by `kind`; handlers must declare idempotency expectations
- [X] T037 [US3] Implement `backend/src/portalab/core/jobs/worker.py` and wire `portalab worker` in `app/cli.py`: poll loop, per-job timeout, graceful shutdown, structured logs with correlation id

**Checkpoint**: Events (007), Notifications (010), Connectors sync and Automations can all publish/consume through one primitive.

---

## Phase 5: User Story 8 — Privacy-ready data foundation (P2)

**Goal**: every module is export/erasure/retention-compatible by construction; append-only integrity is enforced by the database.
**Independent test**: registered model → `personal_columns()` lists its PII; tombstone scrubs only those columns and keeps the id;
UPDATE/DELETE on an append-only table is rejected by the DB. (Plan §5; the visibility engine itself is spec 021.)

### Tests first

- [X] T038 [P] [US8] Write `backend/tests/integration/test_append_only.py`: UPDATE and DELETE on a table marked append-only fail at the database level; INSERT of a correction row succeeds
- [X] T039 [P] [US8] Write `backend/tests/unit/test_pii_registry.py`: classification classes (`identifier|contact|profile|preference|activity|content|technical`), `personal_columns(model)`, failure on an unclassified PII-named column
- [X] T040 [P] [US8] Write `backend/tests/integration/test_tombstone.py`: scrub nulls registered PII columns only, preserves `id` and foreign keys, is idempotent

### Implementation

- [X] T041 [P] [US8] Implement `backend/src/portalab/core/privacy_registry.py`: column classification decorator/metadata + registry API
- [X] T042 [P] [US8] Implement `backend/src/portalab/core/append_only.py`: migration helper creating the trigger that rejects UPDATE/DELETE on declared tables
- [X] T043 [US8] Implement `backend/src/portalab/core/tombstone.py`: generic registry-driven PII scrub (no table names hard-coded), idempotent
- [X] T044 [US8] Add a CI test in `backend/tests/boundary/test_pii_classification.py` failing when a mapped column named like PII (`email`, `name`, `ip`, `token`, …) is neither classified nor explicitly marked non-personal

---

## Phase 6: User Story 9 — Administration-ready configuration & secrets boundary (P2)

**Goal**: modules can *declare* settings and protect credentials without any module owning a config store (CD-011).
**Independent test**: declared settings are validated and enumerable; secrets round-trip encrypted and never appear in logs/errors.
(Plan §8; the Administration store and first-run wizard are spec 020 / Configuration step.)

### Tests first

- [X] T045 [P] [US9] Write `backend/tests/unit/test_secretbox.py`: encrypt/decrypt round-trip with per-record nonce, wrong key fails safely, representation never prints the secret
- [X] T046 [P] [US9] Write `backend/tests/unit/test_declare_setting.py`: scope/key/schema/default validation, duplicate key rejected, hierarchy scopes `Global|Module|Plugin|User`, sensitive flag

### Implementation

- [X] T047 [US9] Implement `backend/src/portalab/core/secrets.py`: `SecretBox` (application-key encryption, write-only wrapper type, redaction hook shared with logging)
- [X] T048 [US9] Implement `backend/src/portalab/core/config_declaration.py`: `declare_setting(scope, key, schema, default, user_overridable, sensitive, version)` and an in-memory declaration catalog — **contract only; no persistence, no resolution** (those land in the Configuration step)

---

## Phase 7: User Story 4 — Independent regions & live updates (P1)

**Goal**: parallel, non-blocking requests (classic search vs AI later) and live pushes over one SSE channel.
**Independent test**: SSE stream delivers only what the caller may see and survives reconnects; one region failing leaves the others rendered.

### Tests first

- [X] T049 [P] [US4] Write `backend/tests/integration/test_stream.py`: `GET /api/v1/stream` requires authorization, filters events by the `Authorizer` port, supports `Last-Event-ID` resume, and a slow consumer does not block producers
- [X] T050 [P] [US4] Write `frontend/tests/unit/regions.test.tsx`: two regions load independently; a failing region renders its error state while the other renders data

### Implementation

- [X] T051 [US4] Implement `backend/src/portalab/app/stream.py`: SSE endpoint fed from the outbox/jobs primitive, permission-filtered, heartbeat + resume
- [X] T052 [P] [US4] Implement `frontend/src/state/regions.tsx` and `frontend/src/api/stream.ts`: independent data-region boundary (TanStack Query) + SSE client with backoff reconnect

---

## Phase 8: User Story 1 — Unified-environment frontend scaffold (P1)

**Goal**: the SPA foundation the real shell (spec 004) and design system (spec 022) will build on.
**Independent test**: the app builds, renders a placeholder shell, every functional state renders accessibly under two token themes, and the typed API client matches the OpenAPI schema.

### Tests first

- [X] T053 [P] [US1] Write `frontend/tests/a11y/functional-state.test.tsx`: each of the 10 functional states renders with a non-color cue (icon/text) and passes axe under two token sets and `prefers-reduced-motion`
- [X] T054 [P] [US1] Write `backend/tests/contract/test_openapi_snapshot.py`: OpenAPI schema equals the committed snapshot (breaking-change guard)

### Implementation

- [X] T055 [P] [US1] Create design tokens in `frontend/src/design-system/tokens.css` (colors, type scale, density, motion as CSS custom properties) and two example themes in `frontend/src/design-system/themes/{light,dark}.css`; themes change appearance only (CD-022)
- [X] T056 [US1] Implement `frontend/src/design-system/FunctionalState.tsx`: standardized states `loading|available|partial|stale|error|unavailable|maintenance|unauthorized|no-data|syncing` with icon+text, never color-only (FR-004/CD-027)
- [X] T057 [US1] Create the placeholder shell `frontend/src/shell/AppShell.tsx` and `frontend/src/main.tsx`: landmark layout, skip link, keyboard-focusable navigation slot, no business logic
- [X] T058 [US1] Add `gen:api` (OpenAPI → typed client into `frontend/src/api/generated/`) and a drift check script `frontend/scripts/check-api-drift.mjs` used by CI

---

## Phase 9: Polish, packaging & validation (plan WP6/WP7)

- [X] T059 Create the multi-stage `deploy/Dockerfile` (build frontend → copy into backend image → one image with `serve|worker|migrate` entrypoints, non-root user) and `deploy/docker-compose.yml` (`postgres`, `portalab`, `worker`, secrets via `*_FILE`)
- [X] T060 Complete `.gitlab-ci.yml` `test` (PostgreSQL service, backend unit+integration, migrations upgrade, frontend Vitest/axe), `build` (Docker image) and tag-only `publish` stages with `ENABLE_*` toggles like the sibling pipelines
- [X] T061 Create `scripts/smoke.sh` implementing the 8 acceptance checks of `quickstart.md` (health/readiness, boundary lint failure on a forbidden import, migration upgrade, job dedup + crash re-claim, default-deny, log correlation/no secrets, API drift, single image as serve and worker)
- [X] T062 Add the migration upgrade-from-previous-release test scaffold `backend/tests/integration/test_migration_upgrade.py` (fixture dump of the previous schema; initially one revision) so every later spec's migration is tested the same way
- [X] T063 Update the root `CLAUDE.md` "Commands" section with the real commands once T001–T062 exist (remove the "Planned" note)
- [X] T064 Run the full validation: `ruff`, `mypy`, `lint-imports`, backend tests, frontend lint/typecheck/test, `scripts/smoke.sh`; record results in the PR/commit notes

---

## Dependencies & Execution Order

- **Setup (1)** → **Foundational (2)** blocks everything. Within Phase 2: tests T007–T009 first; T010–T013 parallel; T014 → T015 → T016; T017 needs T012–T013 + T015; T018/T019 after T015/T016; T020 → T021–T023.
- **Story phases** (after Phase 2), in priority order but mostly independent:
  - **US2 (3)** needs T015, T012; **US3 (4)** needs T015, T016, T013; **US8 (5)** needs T015, T016; **US9 (6)** needs T013 (redaction), independent of the DB; **US4 (7)** needs US3 (outbox) + T017; **US1 (8)** needs T003 only (frontend) + T054 needs T017.
- **Polish (9)** after all chosen stories.
- Cross-spec: none required to *start* — Auth/Permissions plugs into the `Authorizer` port (T017), Configuration into `declare_setting` (T048), Events into the job/outbox primitive (T035), Connectors into the capability kit (T029).

## Parallel Opportunities

- After T002: T003, T004, T005, T006 together.
- Phase 2: T007–T009 together; T010–T013 together; T021–T023 together.
- After Phase 2: **US2, US3, US8, US9, US1-frontend can proceed in parallel** (disjoint files: `capabilities/`, `core/jobs/`, `core/{privacy_registry,append_only,tombstone}`, `core/{secrets,config_declaration}`, `frontend/`); US4 follows US3.

## Implementation Strategy

- **MVP = Setup + Foundational + US2 + US3**: a bootable, migrating, default-deny kernel with the capability registry and the durable job/outbox primitive — enough to start Phase 1 Auth/Configuration and Phase 2 Events/Connectors planning on real contracts.
- Then US8 + US9 (privacy/config contracts), US4 + US1 (transport + frontend scaffold), then Polish.
- Commit after each coherent unit (a test group + its implementation); never one giant commit.

## Traceability (plan → tasks)

| Plan work package | Tasks |
|---|---|
| WP1 scaffold + tooling + CI skeleton | T001–T006 |
| WP2 kernel (`db`, `ids`, `time`, `errors`, `logging`, `secrets`, settings) | T007–T023, T047 |
| WP3 job/outbox primitive | T031–T037 |
| WP4 capability registry + module loader + boundary lint | T024–T030 |
| WP5 frontend scaffold | T003, T050, T052–T058 |
| WP6 image + compose + CLI | T019, T059–T060 |
| WP7 conventions test-kit | T020, T029–T030, T038–T044, T061–T062 |
| Plan §5 privacy conventions | T038–T044 |
| Plan §8 config/secret boundary | T014, T045–T048 |
| Plan §9 testing strategy | tests-first tasks in every phase |
| Plan §10 CI | T006, T060 |
| Plan §14 risks | R-A → T017 (`Authorizer`/audit port boundary), R-B → T010, R-C → T020 |

## Notes

- Total: **64 tasks** — Setup 6 · Foundational 17 · US2 7 · US3 7 · US8 7 · US9 4 · US4 4 · US1 6 · Polish 6.
- Tests precede implementation in each phase and must fail first.
- No product rule is introduced; every mechanism is a primitive or contract whose behaviour is owned by the cited spec.
