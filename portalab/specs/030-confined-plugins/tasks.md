# Tasks: Confined Extensions

**Input**: Design documents from `/specs/030-confined-plugins/` (plan.md, spec.md, research.md R1–R17,
data-model.md, contracts/, quickstart.md)
**Prerequisites**: spec 023 as built (`modules/plugins`, `sdk`, `plugins_runtime`, `PluginGuard`,
`PluginStorage`), 028's sandbox, 029's exposure catalog (`impl/029-interfaces-catalog`).
**Tests**: requested — every success criterion maps to a suite (quickstart.md).
**Implementation branch**: `impl/030-confined-plugins` from `impl/029-interfaces-catalog` (POC worktree);
paths are relative to `portalab/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 (confinement), US1b (one package, slots), US2 (Forum), US3 (Chat), US4 (product type),
  US5 (outside services), US6 (023 compatibility), US7 (authoring)

## Phase 1: Setup

- [ ] T001 Create the package `backend/src/portalab/plugins_runtime/confined/__init__.py` and register it in `backend/importlinter.ini` (importable by `modules/plugins` only; it imports `core` and `sdk` only)
- [ ] T002 [P] Create the test folders `backend/tests/{unit,integration,security,migrations}/plugins/confined/` with `conftest.py` fixtures (a plugin folder factory, a running host fixture) and `backend/tests/fixtures/plugins/probe/` skeleton
- [ ] T003 [P] Add the 030 settings declarations (`plugins.allowUnconfined`, `plugins.allowWeakConfinement`, `plugins.jobTimeoutSeconds`, `plugins.concurrentCalls`, `plugins.memoryMb`, `plugins.storageQuotaMb`, `security.egressAllowList`, `security.egressHosts`, `security.moduleRoles`, `audit.offsite`) in `backend/src/portalab/modules/plugins/settings.py` and `backend/src/portalab/modules/administration/` settings registry

## Phase 2: Foundational (blocks every story)

- [ ] T004 Write unit tests for the kernel builders (BPF program shape per architecture, Landlock rule sets, rlimits plan, `probe()` result) in `backend/tests/unit/plugins/confined/test_kernel.py`
- [ ] T005 Implement `backend/src/portalab/plugins_runtime/confined/kernel.py`: `probe()` (Landlock ABI, seccomp availability), `confine(paths, scratch, memory_mb)` applying no_new_privs, rlimits, Landlock (fs + TCP, scopes when ABI ≥ 6) and the seccomp filter of R2 via `ctypes` (x86_64 and aarch64 syscall tables)
- [ ] T006 [P] Write unit tests for framing and limits (1 MiB lines, malformed JSON, ids) in `backend/tests/unit/plugins/confined/test_protocol.py`
- [ ] T007 [P] Implement `backend/src/portalab/plugins_runtime/confined/protocol.py` (message types of contracts/child-protocol.md, encoder/decoder, `Oversize`, async line reader with limit)
- [ ] T008 Implement the recording context `backend/src/portalab/plugins_runtime/confined/recording.py`: 023's `PluginContext` surface recording contributions and handler ids, plus `db`, `portal`, `http`, `live`, `settings`, `notify`, `emit`, `enqueue` that send `ask` messages
- [ ] T009 Implement the child entry `backend/src/portalab/plugins_runtime/confined/child.py`: confine first (report `confined`), read `hello`, import the entry point from the installed version, run `register(ctx)`, send `registered`/`ready`, serve `call`s concurrently, answer `ping`, handle `stop`
- [ ] T010 Implement `backend/src/portalab/plugins_runtime/confined/host.py` `ConfinedHost`: spawn `python -I -m …child` with an empty environment, scratch folder under `data_dir/plugins-run/<key>`, pipes, stderr capture; `start`, `call(hid, args, deadline)`, `stop`, heartbeat, restart with backoff, concurrency limit, attempt callback, ask dispatcher hook
- [ ] T011 Write integration tests for the host (start/registered/ready, call round trip, timeout, crash and restart, oversize, busy, stop) with a tiny fixture plugin in `backend/tests/integration/plugins/confined/test_host.py`
- [ ] T012 Extend the manifest to version 2 in `backend/src/portalab/modules/plugins/manifest/schema.py` (runtime, `[capabilities]`, `[[routes]]` labels, slots, secret settings with `inject`; v1 implied runtime) with unit tests in `backend/tests/unit/plugins/test_manifest_v2.py` covering every blocking finding of contracts/manifest-v2.md
- [ ] T013 Add the migration `backend/migrations/plugins/versions/…_plugins_00NN_confined.py`: columns `runtime`, `confinement`; tables `grants`, `attempts` (append-only trigger), `network_calls`, `secret_settings`, `slot_settings`, `confirmations`; data step setting `plugins.allowUnconfined` from installed in-process code plugins; models in `backend/src/portalab/modules/plugins/models/__init__.py`
- [ ] T014 Implement the grants service `backend/src/portalab/modules/plugins/grants/service.py` (requested capabilities with plain-words descriptions en/fr from `backend/locales/{en,fr}/plugins.json`, accept for a version, revoke now, `allowed(key, capability, parameter)`), audited (013/020 audit port)
- [ ] T015 Implement the ask dispatcher `backend/src/portalab/modules/plugins/capabilities/__init__.py` routing each `cap` to its handler after the grant check, recording `denied_*` attempts through `PluginGuard`
- [ ] T016 Wire confined plugins into the lifecycle `backend/src/portalab/modules/plugins/lifecycle/service.py`: choose runtime from the manifest, held states (`held_unconfined`, `held_confinement`), start hosts in `serve` and `worker` (`backend/src/portalab/app/main.py`, worker entry), install proxies into 023's registries from `registered`, withdraw on stop/quarantine

**Checkpoint**: a fixture confined plugin starts, registers a route and answers it; nothing reachable outside.

## Phase 3: User Story 1 — A plugin installed unknowingly cannot harm the portal (P1) 🎯 MVP

**Goal**: every forbidden capability fails, is recorded, and quarantines past the threshold.
**Independent test**: quickstart §1 and §2.

- [ ] T017 [P] [US1] Build the probe plugin `backend/tests/fixtures/plugins/probe/` (manifest v2 with storage only; one route per probe, run only when the test asks; neutral descriptions)
- [ ] T018 [US1] Write the isolation campaign `backend/tests/security/plugins/test_confinement.py` (SC-001: each probe refused, one attempt row each, core row counts and file hashes unchanged)
- [ ] T019 [US1] Implement storage as the plugin's login role `backend/src/portalab/modules/plugins/capabilities/storage.py` (password in `secret_settings.__db`, per-plugin asyncpg pool, one statement, refused first keywords, `statement_timeout`, caps, quota measure and read-only mode) and extend `backend/src/portalab/modules/plugins/db/plugin_db.py` provisioning (LOGIN, CONNECTION LIMIT 3)
- [ ] T020 [P] [US1] Unit tests for the statement filter and caps in `backend/tests/unit/plugins/test_storage_filter.py`; integration tests (`RESET ROLE`, `set_config('role')`, core table, quota) in `backend/tests/integration/plugins/confined/test_storage.py`
- [ ] T021 [US1] Record limit breaches (memory via child exit status, timeout, oversize, busy, crash) as attempts and feed `PluginGuard` quarantine; close the plugin's live topics and stop its host on quarantine in `backend/src/portalab/modules/plugins/guard/guard.py` and `host.py`
- [ ] T022 [US1] Write the containment journey test `backend/tests/integration/plugins/test_containment.py` (SC-002: core journeys pass while the probe crashes, hangs and floods; quarantine; Admin notified)
- [ ] T023 [US1] Expose `GET /admin/plugins/runtime` and attempts (`GET /admin/plugins/{key}/attempts`) in `backend/src/portalab/modules/plugins/api/admin.py`; `portalab plugin runtime` CLI in `backend/src/portalab/app/plugin_cli.py`
- [ ] T024 [P] [US1] Admin UI: runtime status, warning banners (weak, unconfined), attempts list and quarantine reason in `frontend/src/features/admin/plugins/` with unit tests in `frontend/tests/unit/plugins/admin-attempts.test.tsx`

## Phase 4: User Story 2 — A plugin adds a complete feature: a forum (P1)

**Goal**: Forum installs, is reviewed, used end to end; disabling keeps data.
**Independent test**: quickstart §3.

- [ ] T025 [P] [US2] Contract tests for the dispatcher with confined routes and labels (`read`, `action`, `committing`) in `backend/tests/contract/plugins/test_confined_routes.py`
- [ ] T026 [US2] Implement committing confirmations `backend/src/portalab/modules/plugins/confirmations.py` (describe handler, token bound to member/plugin/route/body hash, single use, 5 min) and use them in `backend/src/portalab/modules/plugins/api/runtime.py`
- [ ] T027 [US2] Implement portal data `backend/src/portalab/modules/plugins/capabilities/portal.py`: operation lookup in the exposure catalog, accepted list, in-process ASGI call with `portalab.acting_principal` honoured by the auth dependency in `backend/src/portalab/core/authorization.py` (header of that name ignored), plugin principal for jobs; tests in `backend/tests/integration/plugins/confined/test_portal_calls.py`
- [ ] T028 [US2] Proxy events, jobs, notifications, search providers and privacy export/erase through the host in `backend/src/portalab/modules/plugins/capabilities/{events,jobs,notify}.py` and the 023 registries (`context/registries.py`), with tests in `backend/tests/integration/plugins/confined/test_proxies.py`
- [ ] T029 [US2] Widen declarative blocks (`actions`, `cards`, `thread`, `live`) in `backend/src/portalab/sdk/pages.py` and `api/runtime.py` serialisation; front renderers in `frontend/src/features/plugins/blocks/` with unit tests `frontend/tests/unit/plugins/blocks.test.tsx`
- [ ] T030 [US2] Front confirmation for committing plugin operations (`PluginConfirm` using the design system's `ConfirmDialog`, summary drawn by Portalab, resend with token) in `frontend/src/features/plugins/PluginConfirm.tsx` with tests `frontend/tests/unit/plugins/confirm.test.tsx`
- [ ] T031 [US2] Admin review of capabilities (plain words, accept all, revoke, per version; update needing more keeps the previous version) in `frontend/src/features/admin/plugins/Review.tsx` and API `PUT /admin/plugins/{key}/versions/{v}/grants`, `DELETE …/grants/{capability}`
- [ ] T032 [US2] Write the Forum example `examples/plugins/forum/` (manifest v2, migrations, topics/posts, permissions read/post/moderate, nav, pages with `thread`, committing publish with describe, notifications to followers, search provider, event `topic_posted`, privacy export/erase)
- [ ] T033 [US2] Integration test `backend/tests/integration/plugins/test_forum.py` (install, review, enable, post with confirmation, notify, search, export, disable keeps data, re-enable) and e2e `frontend/tests/e2e/plugins/forum.spec.ts` (API stubbed)

## Phase 5: User Story 6 — 023's plugins keep working (P2, slice A)

**Goal**: declarative unchanged; in-process code kept running on upgrade; migration keeps data.
**Independent test**: quickstart §6.

- [ ] T034 [US6] Hold in-process code plugins when `plugins.allowUnconfined` is false (`held_unconfined`, message how to migrate) and show a permanent warning when true, in `lifecycle/service.py` and `frontend/src/features/admin/plugins/`
- [ ] T035 [US6] Ship `examples/plugins/hello` 2.0.0 with `runtime = "confined"` (same data) alongside 1.0.0 fixtures; migration test `backend/tests/migrations/test_plugins_runtime_upgrade.py` (upgrade sets the switch; fresh install holds v1 code; v2 keeps 100% rows)
- [ ] T036 [US6] Run 023's suites unchanged and fix regressions (`backend/tests/**/plugins/` without `confined`)

## Phase 6: User Story 5 — An outside service through listed hosts only (P2, slice A)

**Goal**: listed hosts reachable, others refused and recorded; secrets never read by the plugin.
**Independent test**: quickstart §8.

- [ ] T037 [US5] Implement `backend/src/portalab/modules/plugins/capabilities/network.py` (scheme/host/port check, resolution and private-range refusal, connect to the resolved address, no cross-host redirects, limits, recording in `network_calls`, injection of secret settings)
- [ ] T038 [US5] Secret settings: `PUT/DELETE /admin/plugins/{key}/secrets/{name}` (write-only, audited, `SecretBox`, redaction registration) in `grants/` API and the admin form field in `frontend/src/features/admin/plugins/Settings.tsx`
- [ ] T039 [P] [US5] Unit tests for the SSRF guard in `backend/tests/unit/plugins/test_network_guard.py`; security test `backend/tests/security/plugins/test_secrets.py` (SC-008)

## Phase 7: User Story 1b — One extension changes the experience as a whole (P1, slice B)

**Goal**: one package brings code, slot contributions and looks; members and Admin control them.
**Independent test**: quickstart §9 and §10.

- [ ] T040 [US1b] Slots registry and API `backend/src/portalab/modules/plugins/slots/` (closed list R10, contributions from manifests and `registered`, deterministic order with `slot_settings`, member `ui.hiddenContributions`, `GET /plugins/slots`, `GET /plugins/{key}/slots/{id}/data`) with tests `backend/tests/integration/plugins/test_slots.py`
- [ ] T041 [US1b] Front slot host `<Slot name context>` in `frontend/src/features/plugins/Slot.tsx` (fetch once per view, blocks drawn by Portalab, 028 elements sandboxed, hide for me) and place it in the shell nav, home, media detail, person page, profile, member settings and admin settings
- [ ] T042 [US1b] Player slots `player.overlay` (time windows) and `player.button` in `frontend/src/features/media/player/VideoPlayer.tsx` (no stream handed; go-to-time and form actions performed by the player)
- [ ] T043 [US1b] Portalab's own home sections and nav entries as `core:` contributions orderable by extensions (defaults) and restorable by members (`ui.coreOrder`); Admin order/visibility page `frontend/src/features/admin/plugins/Slots.tsx`
- [ ] T044 [US1b] One package lifecycle: a package's 028 elements imported, analysed and enabled with the plugin version; blocked as a whole on refusal (`modules/plugins/lifecycle/service.py` ↔ `modules/visuals`)
- [ ] T045 [US1b] Write `examples/plugins/moments/` and `examples/plugins/home-sections/`; e2e `frontend/tests/e2e/plugins/moments.spec.ts` (SC-009) and `frontend/tests/e2e/plugins/home-sections.spec.ts`; performance test `frontend/tests/unit/plugins/slots-performance.test.tsx` (SC-010)

## Phase 8: User Story 3 — A live feature: an internal chat (P2, slice C)

**Independent test**: quickstart §4.

- [ ] T046 [US3] Implement `backend/src/portalab/modules/plugins/capabilities/live.py` (topics `plugin.<key>.<topic>`, audience, author blocks removed, size and rate limits) and presence notices from SSE subscriptions (`backend/src/portalab/app/stream` subscriber hooks)
- [ ] T047 [US3] Write `examples/plugins/chat/` (rooms, direct messages, presence, mentions, moderation, flood limits) and the front `live` block refresh
- [ ] T048 [US3] Integration test `backend/tests/integration/plugins/test_chat_live.py` (SC-004 p95 ≤ 1 s with 50 subscribers, blocks, moderation, flood)

## Phase 9: User Story 4 — A new kind of product in the shop (P2, slice C)

**Independent test**: quickstart §7.

- [ ] T049 [US4] Proxy product type hooks (activate, deactivate, refund) with 10 s deadline through `modules/plugins/activation/service.py`; card as blocks or 028 element
- [ ] T050 [US4] Write `examples/plugins/commission/` and `backend/tests/integration/plugins/test_commission.py` with fault injection (raise, timeout, child killed) — SC-007

## Phase 10: User Story 7 — Authoring (P3, slice D)

**Independent test**: quickstart §12.

- [ ] T051 [P] [US7] SDK 2.0 additions and docs in `backend/src/portalab/sdk/__init__.py`, `sdk/slots.py`; `docs/plugins/confined.md` (migration guide from 023)
- [ ] T052 [US7] `portalab plugin new` template and `portalab plugin simulate` (confined child against a simulated parent: temp schema storage, sample portal answers, network refused unless `--allow-host`) in `backend/src/portalab/app/plugin_cli.py` and `plugins_runtime/confined/simulator.py`
- [ ] T053 [US7] `portalab plugin validate` capability report in the Admin's words and every blocking finding; tests `backend/tests/unit/plugins/test_validate_report.py`; every example validated in CI

## Phase 11: Deployment hardening (#144, slice D)

- [ ] T054 Outbound allow-list `backend/src/portalab/app/egress.py` hooked into every HTTP client factory (`connectors/http_base.py`, pack sources, sign-in providers, plugin network); test `backend/tests/integration/security/test_egress.py`
- [ ] T055 [P] `read_only` + `tmpfs` in `deploy/compose.example.yml`; `portalab doctor` checks (user, writable code, egress, module roles, audit sink) in `backend/src/portalab/app/cli.py`
- [ ] T056 Audit copied off the machine `backend/src/portalab/modules/administration/audit_offsite.py` (syslog RFC 5424 TCP/TLS, JSON-lines file) with `backend/tests/integration/audit/test_offsite.py`
- [ ] T057 Per-module database roles behind `security.moduleRoles` in `backend/src/portalab/core/db.py` and a migration creating `portalab_<schema>` roles; run the suite with it on; list and fix cross-schema reads; test `backend/tests/integration/security/test_module_roles.py`

## Phase 12: Polish & cross-cutting

- [ ] T058 [P] i18n en/fr for every new string (`backend/locales/{en,fr}/plugins.json`, `admin.json`), ICU plurals for counts, no reserved words in keys
- [ ] T059 [P] Accessibility sweep (axe) of the review, attempts, secrets, slots pages and plugin blocks in `frontend/tests/e2e/plugins/a11y.spec.ts`
- [ ] T060 Regenerate `backend/openapi.json` and `frontend/src/api/generated/schema.ts`; drift check
- [ ] T061 Full gates (backend suite, ruff, mypy, import-linter; front lint, typecheck, tests, build; e2e plugins) and the quickstart on the POC (live, nothing committing confirmed)

## Dependencies

- Setup → Foundational (T004–T016) → every story.
- US1 (T017–T024) first (MVP); US2 needs T019 (storage) and T026–T031; US6 and US5 after Foundational, in
  parallel with US2; US1b after US2's blocks (T029); US3 needs US1b's `live` block; US4 after Foundational;
  US7 after US2; hardening T054 needs US5's network (T037); T057 last.

## Parallel examples

- Foundational: T006/T007 (protocol) alongside T004/T005 (kernel).
- US1: T017 (probe) and T020 (storage tests) while T019 is written.
- US5: T039 tests alongside T037.
- Polish: T058, T059 together.

## Implementation strategy

MVP = Phases 1–3 (confinement proven by the isolation campaign). Then slice A (US2, US6, US5), slice B
(US1b), slice C (US3, US4), slice D (US7, hardening), polish. Each slice is validated on the POC before the
next.
