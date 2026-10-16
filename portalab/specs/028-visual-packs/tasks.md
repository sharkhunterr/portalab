---
description: "Task list for 028 — Visual Packs"
---

# Tasks: Visual Packs (Every Look as a Pack, Visual Import Workflow, Pack Navigations, Booster Scenes, Widgets, Minimal Public Surface)

**Input**: Design documents from `/specs/028-visual-packs/`
**Prerequisites**: plan.md, spec.md, research.md (R1–R35), data-model.md, contracts/api-contracts.md,
contracts/pack-format.md, contracts/sandbox-protocol.md, contracts/cli-contracts.md, contracts/ui-contracts.md,
quickstart.md

**Tests**: Included — the constitution (VIII) requires every acceptance criterion to be test-verifiable, and
quickstart.md maps SC-001…SC-010 to automated checks.

**Starting point**: the proof of concept (branch `poc/visual-packs`, commits `5c2339b`, `da9a837`, `50175ef`)
is already in this branch's history: tasks **move and complete** its code rather than rewrite it.

**Organization**: grouped by user story (spec priorities: US1–US3 P1, US4/US5/US7 P2, US6/US8 P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1…US8 from spec.md
- Paths are relative to `portalab/` (backend in `backend/`, SPA in `frontend/`, built-in packs in `packs/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: module skeleton, fixtures and the frozen safety net for the built-in move.

- [X] T001 Create the module skeleton `backend/src/portalab/modules/visuals/{__init__.py,module.py,models/__init__.py,api/__init__.py}` and register it in `backend/src/portalab/app/wiring.py` (constructed after `ui` and `marketplace`, `visuals_root=data_dir / "visuals"`); add `portalab.modules.visuals` to the module contracts of `backend/importlinter.ini` (R1)
- [X] T002 [P] Generate the frozen fixture `tests/fixtures/builtin-looks-before.json` with a script `backend/scripts/freeze_builtin_looks.py`: every product key of `app/demo_shop.py` with its type, payload look and economy, every look key per family from `capabilities/themes.py` and `capabilities/visuals.py`, every built-in theme key from `modules/ui/themes/builtin/*.json`, every frontend look key (exported from `fxLooks.ts`, `palettes.ts`, `cosmetics.ts` by `frontend/scripts/list-looks.mjs`) (R8)
- [X] T003 [P] Create test pack fixtures in `backend/tests/fixtures/visual-packs/`: `valid-minimal/` (one CSS frame), `blocking/` (CSS out of scope + unknown type), `scripts/` (one JS celebration), `replaces/` (a look claiming a built-in key), `v1/` and `v2/` of one pack (v2 drops an element), `malformed/` generators (traversal, link, NUL, oversize, forbidden kind) built at test time, never committed as archives
- [X] T004 [P] Add the new i18n namespaces/keys skeleton for the workflow and findings in `backend/locales/{en,fr}/admin.json` (`visuals.step.*`, `visuals.finding.<code>`, `visuals.state.*`, `visuals.action.*`), respecting the i18n lint (no `pass/token/key` in keys, ICU plurals for `{count}`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the registry in PostgreSQL, the moved POC code, permissions, cache and file serving that every
story builds on.

**⚠️ CRITICAL**: no user-story work starts before this phase is complete.

- [X] T005 Write migration `backend/migrations/visuals/versions/20261215_0900_visuals_0001_registry.py` (branch label `visuals`, depends on `core_0005`): schema `visuals`, tables `packs`, `pack_versions`, `elements`, `look_claims`, `scene_bindings`, `registry_epoch` with the checks, unique and partial indexes of data-model.md
- [X] T006 [P] SQLAlchemy models for the six tables in `backend/src/portalab/modules/visuals/models/__init__.py`
- [X] T007 Move the POC code `backend/src/portalab/modules/ui/visuals/{manifest,analysis,store,github,sandbox}.py` to `backend/src/portalab/modules/visuals/` (imports updated, `ui/visuals/` removed); widen `manifest.py`'s type vocabulary to data-model `elements.type` (scene parts, `widget`, `widget_style`, `theme_pack`) and render kinds `data`, `renderer` (R9)
- [X] T008 Registry repository `backend/src/portalab/modules/visuals/registry.py`: packs/versions/elements CRUD, `live()` (enabled packs' current versions), claims read/write, `bump_epoch()` in the same transaction; replaces the JSON file of the POC service (R2)
- [X] T009 Epoch cache `backend/src/portalab/modules/visuals/cache.py`: active manifest and open vocabulary per epoch, refreshed on `visuals.changed` or when the stored epoch is newer (checked at most every 10 s); `capabilities/visuals.py` `external_looks` renamed `live_looks` and fed from it (R4)
- [X] T010 Declare the reserved permission `visuals.manage` (sensitive, reserved, requires confirmation) in `backend/src/portalab/modules/authz/catalog/core_permissions.py`; replace `APPEARANCE_MANAGE` on every visuals route; update `tests/security/authz/test_permission_matrix.py` (R17)
- [X] T011 Declare events `visuals.changed`, `visuals.pack.{published,switched,rolled_back,archived,removed,purged}`, `visuals.element.failed` in `backend/src/portalab/modules/visuals/module.py` (outbox) and publish `visuals.changed` to the live stream (audience everyone) on every epoch bump (R4)
- [X] T012 Members API `backend/src/portalab/modules/visuals/api/members.py`: `GET /visuals/active` (ETag = epoch, 304), `GET /visuals/files/{pack}/{sha16}/{path}` (live versions only), `GET /visuals/sandbox` **with a session** (no longer `@public`) — inert headers and extension allow-list of R12; remove `/api/v1/visuals/sandbox` from `tests/integration/test_default_deny.py`'s allow-list
- [X] T013 Admin file route `GET /admin/visuals/files/{pack}/{sha16}/{path}` (any version, `visuals.manage`) in `backend/src/portalab/modules/visuals/api/admin.py`
- [X] T014 Data step of `visuals_0001`: import the POC's `DATA_DIR/visuals/state.json` when present (packs, versions, reports, decisions, enabled flags) into the tables at module start-up (`modules/visuals/module.py`, once, then rename it `state.json.migrated`) (data-model « Data migrations » 1)
- [X] T015 [P] Move the frontend POC code `frontend/src/design-system/themes/external/*` to `frontend/src/design-system/visuals/` (`registry.ts` = former `external.ts`, `cssGuard.ts`, `sandbox.ts`, `ExternalScript.tsx`, `ExternalVisualsLoader.tsx`), update imports, and refetch `GET /visuals/active` on the live event `visuals.changed` (else every 60 s) (R4, R11)
- [X] T016 [P] `resolveLook(family, key)` in `frontend/src/design-system/visuals/resolve.ts`: live element → interface default → socle default; used by every look consumer (frames, banners, names, badges, level-ups, celebrations, notifications, palettes, ambients) (R22)
- [X] T017 [P] Tests for the foundation: `backend/tests/migrations/test_visuals_0001.py` (upgrade/downgrade, POC state import), `backend/tests/unit/visuals/test_registry.py` (claims PK conflicts, epoch bump), `backend/tests/integration/visuals/test_files.py` (live vs admin access, inert headers, 404 off, sandbox requires a session), `frontend/tests/unit/visuals/resolve.test.ts`

**Checkpoint**: the POC works on the new registry (import, publish, switch, files, sandbox) with `visuals.manage`.

---

## Phase 3: User Story 1 — The Admin imports a pack through a guided, visual workflow (Priority: P1) 🎯 MVP

**Goal**: six visible steps per version, decisions kept with it, nothing published unseen.

**Independent Test**: import the example pack from the inbox; each step shows its result; validate with one
price changed; the elements appear in the shop with that price; a blocking version cannot pass.

### Tests for User Story 1

- [X] T018 [P] [US1] `backend/tests/unit/visuals/test_workflow_states.py`: step transitions of data-model (imported → analysed → tested → reviewed → published; refused; blocking stays at analysed), confirmations required (scripts, replaces, contracts)
- [X] T019 [P] [US1] `backend/tests/integration/visuals/test_workflow.py`: inbox scan, upload, GitHub (mocked httpx: hosts, redirects, sizes), measures, draft, publish with a changed price (product carries it, decision stored), refuse, same version other content refused, audit entries per step, every route refused without `visuals.manage`
- [X] T020 [P] [US1] `frontend/tests/e2e/visual-packs/workflow.spec.ts`: Nordlys from the inbox through the six steps on desktop and phone widths; blocking fixture stops at Analysis

### Implementation for User Story 1

- [X] T021 [US1] Workflow service `backend/src/portalab/modules/visuals/workflow.py`: `scan`, `upload`, `from_github` (POC logic on the registry), outcomes per step, `record_measures`, `save_draft`, `publish` (claims in the transaction, `CatalogWriter.publish`, interface registration through `ui` themes, decision stored, epoch bump, audit), `refuse` (R18)
- [X] T022 [US1] Analysis split into categories `analysis`/`security` with plain-words codes of contracts/pack-format.md in `backend/src/portalab/modules/visuals/analysis.py`; conflicts read from `look_claims`; economy checked against the portal's rules (warnings) (R19)
- [X] T023 [US1] Server-side CSS rules mirror of R15 in `analysis.py` (keyframes/font-face namespacing reported as info; scope, import, address as blocking) and in `frontend/src/design-system/visuals/cssGuard.ts` (keyframes suffixed by element id, `animation(-name)` rewritten, pack `@font-face` families prefixed `pack-<id>-`) with `frontend/tests/unit/visuals/css-guard.test.ts`
- [X] T024 [US1] Admin API `backend/src/portalab/modules/visuals/api/admin.py`: list, scan, upload, github, updates, version detail, measures, draft, publish †, refuse (contracts/api-contracts.md), problems `ui.visual_pack_*`
- [X] T025 [P] [US1] Frontend API client `frontend/src/features/visuals/api.ts` (regenerated types after `npm run gen:api`)
- [X] T026 [US1] Pack list page `frontend/src/features/visuals/PackList.tsx` (cards: source badge, state chip, current version, update available, owners, health; inbox/upload/GitHub/updates actions) with the page kit
- [X] T027 [US1] Version workflow `frontend/src/features/visuals/VersionWorkflow.tsx` + `frontend/src/features/visuals/steps/{ImportStep,AnalysisStep,SecurityStep,TestStep,ReviewStep,ValidationStep}.tsx` (stepper horizontal/vertical, state icons, next action, revisit until published) replacing the POC's `VisualsAdmin.tsx`
- [X] T028 [US1] Test stage `frontend/src/features/visuals/test/TestStage.tsx`: shop card, profile, moment, navigation in phone/tablet/desktop frames; GPU compile + 3 s fps measure, script readiness within 4 s; posts measures; « Try on myself » session-only override in `frontend/src/design-system/visuals/tryOn.ts` (R20)
- [X] T029 [US1] Routes `/admin/visuals` and `/admin/visuals/:pack/:version` in `frontend/src/shell/router/routes.tsx`, navigation entry `ui.visuals` under Administration → Appearance (`backend/src/portalab/modules/shell/builtin.py`, permission `visuals.manage`)
- [X] T030 [P] [US1] Finding and step texts in `frontend/src/i18n` catalogs and `backend/locales/{en,fr}/admin.json` (T004 keys filled)

**Checkpoint**: an imported pack goes through the six steps and reaches the shop with the decided economy.

---

## Phase 4: User Story 2 — The built-in catalog is delivered as packs (Priority: P1)

**Goal**: every built-in look is an element of a built-in pack; nothing lost; sub-packs enabled/disabled.

**Independent Test**: after migration every product, look and interface is available again with the same key
and owners; disabling a universe pack takes its products off sale and its looks fall back; enabling brings
them back.

### Tests for User Story 2

- [X] T031 [P] [US2] `backend/tests/integration/visuals/test_builtin_sync.py`: first run on a seeded pre-migration portal (ownerships, equipped, preferences, admin-changed prices) — every key of `builtin-looks-before.json` held by exactly one built-in element, economy adopted (nothing revised), packs with products enabled; second run is a no-op; a changed built-in version keeps decisions and records `changes`; a new built-in pack arrives disabled; fresh install enables the socle only (R6, R7)
- [X] T032 [P] [US2] `backend/tests/unit/visuals/test_builtin_packs.py`: every folder of `packs/builtin/` passes the analysis with 0 blocking finding; ids reserved; socle unique; every bundle/booster references existing products
- [ ] T033 [P] [US2] `frontend/tests/unit/visuals/builtin-parity.test.ts`: every frontend look key of the fixture resolves to a built-in element; no look CSS/GLSL left in `design-system/themes/` (grep for hook selectors)

### Implementation for User Story 2

- [X] T034 [US2] Decide the split in `packs/builtin/SPLIT.md` + `packs/builtin/split.json` (look/product key → pack id): `portalab-socle` (default interfaces `portalab-dark/-light`, `light`, `dark`, `high-contrast`, free looks, built-in navigations as `renderer`), one pack per universe (from the 47 sold interfaces and their looks), one per season (`season` field), one per HD collection, `portalab-base` for the rest (FR-005)
- [X] T035 [US2] Export the visual catalog entries of `backend/src/portalab/app/demo_shop.py` as JSON (`backend/scripts/export_shop.py`) for the extraction; functional product types (`statistic`, `media_rescue`, `streak_freeze`, `xp_boost`, `special_request`, `service_access`, `access`, `quota`, `early_unlock`, `project_launch`) stay in `demo_shop.py`
- [ ] T036 [US2] Extraction script `frontend/scripts/extract-builtin-packs.mjs`: per look, rules split by hook from `cosmetics.css`, `universe.css`, `levelup.css`, `ambient.css`, `celebration.css`, `skins.css`, `boosters.css`; GLSL from `premium/{shaders,warmShaders,cozyShaders,cosmosShaders}.ts` and `badgeFx.ts`; renderer params for particle/flow/mesh/weather looks; palettes from `palettes.ts`; interfaces from `modules/ui/themes/builtin/*.json`; economy and texts from T035; writes `packs/builtin/<pack>/elements/<look>/element.json` + files (R8) — *2026-10-16: the CSS families done (499 looks, `look.css` in their element, `render: css`; parity of computed styles checked look by look); 2026-10-16 too: the GPU looks — 193 elements hold their effect's fragment (`render: glsl` with shape, radius, stage, start, cycle), the `FX_*` tables and the looks' effects gone from `premium/` (`visuals/gpu.ts` resolves every GPU look from its pack); and the premium ambiences — 68 elements hold their shader (after `COMMON`, or the phone-safe noise: `params.common`) and their layers (`params`: flows, particles, landscape, CSS stand-in; renderer `layers` when no shader), the shader tables gone from `premium/`, « live weather » staying Portalab's renderer; and the palettes — 58 elements hold their colours (`render: data`, `palette`), the code keeping the socle's two for first paint; and the interfaces — 52 elements hold their definition (`theme.json`) and 15 their stylesheet (`theme.css`, 108 rules out of `universe.css`/`player.css`, computed styles unchanged), registered by the packs' synchronisation (the UI's JSON folder gone, the migrations seeding from the packs, the built-in keys and universes read from them, navigations' own words renamable); the interface's bundled copies to follow*
- [ ] T037 [US2] Run the extraction and fix by hand the rules the guard would cut (siblings, `:root`, shared helpers, keyframes shared across looks) until T032 is green; commit `packs/builtin/` — *CSS: done (`:is()` shared between looks split, nth formulas no longer taken for siblings by the guards, the level badge wearing its look itself, reduced-motion rules made `!important`)*
- [ ] T038 [US2] `renderer` kind in the frontend: `frontend/src/design-system/visuals/renderers.ts` maps `particles`, `flow`, `mesh`, `weather`, `nav:<variant>` to the existing runners/components with params validated (zod) (R9)
- [X] T039 [US2] Built-in sync `backend/src/portalab/modules/visuals/builtin.py` (advisory lock; import + analysis; publish without workflow keeping decisions; new pack disabled; `changes` computed; first run adopts existing products' economy and enables packs whose products exist; marks `ui.themes` built-in rows `source="visuals:<pack>"`) and run it from `portalab migrate` and `serve` start (`backend/src/portalab/app/migrations.py`, `app/main.py`) (R6, R7)
- [X] T040 [US2] Reserve built-in ids: `workflow.py` refuses `portalab-*` from inbox/upload/GitHub (`409 ui.visual_pack_reserved`); the socle refuses switch off/archive/remove (`409 ui.visual_pack_socle`)
- [X] T041 [US2] Pack state API `POST /admin/visuals/{pack}/state` † (enable/disable built-in and imported packs; products off sale/back, claims released/taken, interfaces disabled/enabled, epoch bump, audit) in `modules/visuals/lifecycle.py` + `api/admin.py`
- [ ] T042 [US2] Socle bundled for first paint: Vite plugin `frontend/vite/socle-pack.ts` copying the socle files used by the default interfaces into `dist/packs/socle/` (fingerprinted) and a manifest read by `frontend/src/design-system/visuals/registry.ts` before `/visuals/active` answers (R10)
- [ ] T043 [US2] Remove the extracted look code (never the fallbacks: the default interfaces portalab-dark/-light, light, dark, high-contrast and each family's base look stay in the code, referenced by the socle): look rules from the CSS files, look shaders from `premium/*.ts`, look tables from `fxLooks.ts`/`palettes.ts`/`cosmetics.ts` (keep runners and contracts), built-in look tuples from `backend/src/portalab/capabilities/themes.py` (vocabulary now from `live_looks`), `modules/ui/themes/builtin/*.json` (now in packs); visual entries from `demo_shop.py`. **Rule (user, 2026-10-16)**: nothing about looks hard-coded server-side — no look list in `capabilities/themes.py`, no `Literal` of the five families an interface names (`ambient`, `effect`, `level_up`, `notification_style`, `notification_animation` in `modules/ui/themes/definition.py`), no built-in tuple in `LOOK_TYPES`; every extension carries its own elements, an interface names only looks of its own pack or live ones, and the server only lists what the live packs hold (API) — the frontend reads them from there, its `FX_*` tables gone. *2026-10-16: done for the vocabulary — the look tuples, the five `Literal`s and the free looks gone from the server (read from the packs shipped: `capabilities.visuals.shipped_looks`, the socle's free), `GET /visuals/looks` for the interface, the pickers, the theme studio and the shop's editor reading the server's lists (`preferences.ts`/`cosmetics.ts` lists gone); `FX_*` tables, palettes' colours and interfaces' definitions still in the code*
- [X] T044 [US2] First-run choice « whole catalog » (default) / « socle only » in `backend/src/portalab/modules/administration/firstrun/` + wizard step in `frontend/src/features/admin/FirstRunWizard.tsx`; `portalab demo seed` enables every built-in pack (`backend/src/portalab/app/demo_seed.py`)
- [X] T045 [US2] « What changed » panel for built-in packs updated by a release in `frontend/src/features/visuals/BuiltinChanges.tsx`
- [X] T046 [US2] Copy `packs/builtin/` into the image at `/app/packs/builtin` in `deploy/Dockerfile`; bootstrap setting `PORTALAB_BUILTIN_PACKS_DIR` (default `/app/packs/builtin`, repository path in development)

**Checkpoint**: the portal shows exactly what it showed before, every look now coming from a pack.

---

## Phase 5: User Story 3 — A malicious member cannot reach what is forbidden, and is blocked (Priority: P1)

**Goal**: nothing answers a visitor but signing in; a member probing is blocked, persistently, and can be
unblocked from the console.

**Independent Test**: as a member, request admin routes, others' objects and attack-shaped addresses until
blocked; the account stays blocked after signing in again and after a restart; an administrator is alerted
and lifts the block; as a visitor, every route but sign-in answers that a session is needed.

### Tests for User Story 3

- [X] T047 [P] [US3] `backend/tests/security/test_anonymous_surface.py`: walk every registered route + non-existent paths without a session; allow-list answers normally, all else the byte-identical generic 401; `@public` route outside the allow-list fails the test (R27, R34)
- [X] T048 [P] [US3] `backend/tests/integration/identity/test_guard.py`: weighing (POC unit tests moved from `tests/unit/app/test_intrusion_guard.py`), block persisted and enforced across a new process (restart), account blocked across new sign-ins, address blocked only without a session, settings thresholds, `security.block.started` → notification to `security.manage` holders, lift via API
- [X] T049 [P] [US3] `backend/tests/integration/identity/test_guard_console.py`: `portalab security blocks list|lift` (Admin's own block lifted, audit actor `console:<user>`, running process drops the block within 5 s)
- [X] T050 [P] [US3] `backend/tests/integration/test_health_networks.py`: `/healthz`, `/readyz`, `/metrics` only from configured networks; `server.trusted_proxies` honoured; first-run routes answer 401 once completed; `GET /terms` requires a session
- [X] T051 [P] [US3] `frontend/tests/e2e/visual-packs/anonymous.spec.ts`: sign-in page styled and usable without any API call but the allow-list; a guessed lazy chunk answers 401 without a session

### Implementation for User Story 3

- [X] T052 [US3] Anonymous allow-list `ANONYMOUS_ROUTES` + generic 401 problem in `backend/src/portalab/app/security.py` (applied before routing so unknown paths answer the same); self-registration routes only when open; `@public` restricted to the list (R27)
- [X] T053 [US3] SPA gate in `backend/src/portalab/app/spa.py`: `index.html` and `/packs/socle/` for all; `/assets/<chunk>` only if listed in `dist/public-assets.json` or with a session; Vite build step `frontend/vite/public-assets.ts` writing the sign-in closure from the manifest
- [X] T054 [US3] i18n catalogs anonymous only for `auth`, `common`, `errors` in `backend/src/portalab/modules/i18n/api/` + `EXEMPT_GET_PREFIXES` adjusted
- [X] T055 [US3] Health networks and trusted proxies: setting `observability.health.networks` (`backend/src/portalab/modules/observability/settings.py`), bootstrap `server.trusted_proxies` (`backend/src/portalab/core/settings.py`), client address resolution shared by guard/health/auth (`backend/src/portalab/app/client_address.py`), uvicorn `forwarded_allow_ips` from it (`app/cli.py`) (R28)
- [X] T056 [US3] First run closed once completed (`backend/src/portalab/modules/administration/api/routes.py`: GET/POST answer the generic 401 after completion); terms after sign-in (`backend/src/portalab/modules/privacy/api/terms.py` no longer `@public`; sign-in page link removed in `frontend/src/features/auth/`)
- [X] T057 [US3] Port #134 to the module code: overview filtered per permission, providers without permission contribute nothing (`backend/src/portalab/modules/administration/overview/service.py`), test `tests/integration/admin/test_overview_degraded.py` kept
- [X] T058 [US3] Migration `backend/migrations/identity/versions/20261215_1000_identity_security_blocks.py` + model in `backend/src/portalab/modules/identity/models/`
- [X] T059 [US3] Move the guard from `backend/src/portalab/app/intrusion.py` to `backend/src/portalab/modules/identity/guard/{guard.py,store.py,api.py}`: points in memory, blocks in `identity.security_blocks` through a per-process cache (event `security.blocks.changed` or 5 s), session revocation with reason `suspended`, thresholds from settings `security.guard.*` (R29)
- [X] T060 [US3] Events `security.block.started` (→ notifications to `security.manage` holders, replacing the POC's direct call in `app/main.py`) and `security.blocks.changed` (R31)
- [X] T061 [US3] Console command `portalab security blocks list|lift` in `backend/src/portalab/modules/identity/guard/cli.py`, registered in `backend/src/portalab/app/cli.py` (R30, contracts/cli-contracts.md)
- [X] T062 [US3] Security blocks page kept (`frontend/src/features/security/SecurityBlocks.tsx`) on the persisted API (ids instead of keys)

**Checkpoint**: SC-005 and SC-006 hold; a restart keeps blocks; the console lifts any block.

---

## Phase 6: User Story 4 — A pack brings a navigation of its own (Priority: P2)

**Goal**: pack navigations usable on every device, with fallback and never on administration.

**Independent Test**: publish Abysses; its sonar reaches every section on phone/tablet/desktop and with the
keyboard; a failing navigation is replaced within 5 s; administration shows the built-in navigation.

- [X] T063 [P] [US4] `frontend/tests/e2e/visual-packs/navigation.spec.ts`: every section/page reachable at 390/820/1280 px and by keyboard; failing fixture → built-in within 5 s; `/admin/*` built-in; navigate to an ungiven key does nothing
- [X] T064 [P] [US4] `frontend/tests/unit/visuals/pack-nav.test.ts`: key check, rate limit, expand within `nav.expands`, landmark/skip link kept
- [X] T065 [US4] Heartbeat in the sandbox bootstrap (`backend/src/portalab/modules/visuals/sandbox.py`: `ping`/`pong`) and in `frontend/src/design-system/visuals/sandbox.ts` (stop after 3 misses; `ready` within 4 s), reports `POST /visuals/reports` (R14)
- [X] T066 [US4] `POST /visuals/reports` (rate-limited) and element health counts in `modules/visuals/api/members.py` + `registry.py`; event `visuals.element.failed`
- [X] T067 [US4] Harden `frontend/src/shell/nav/PackNav.tsx`: room reserved from `render.nav` before start, fallback to the interface's built-in variant, never mounted under the administration frame, context per sandbox-protocol.md
- [X] T068 [US4] Analysis: an interface naming a navigation its pack does not hold and no live pack provides → blocking (`theme.unknown_reference`) in `modules/visuals/analysis.py` (R22)

**Checkpoint**: SC-007 holds.

---

## Phase 7: User Story 5 — Packs customize the booster scene, or only a booster's composition (Priority: P2)

**Goal**: scene parts from packs around the portal's own draw; compositions from packs or the admin.

**Independent Test**: a pack scene bound to one booster plays its parts; missing parts use the default;
cards and rarities equal the draw; another booster opens with the default; reduced motion: no animation.

- [X] T069 [P] [US5] `backend/tests/integration/visuals/test_scenes.py`: scene analysis (unknown part, durations), binding API, `GET /visuals/scenes/{booster}` default when unbound, composition-only pack publishes a booster with its odds, admin-created boosters untouched
- [X] T070 [P] [US5] `frontend/tests/e2e/visual-packs/booster-scene.spec.ts`: 50 openings, displayed cards/rarities equal the API's draw; partial scene uses default parts; reduced motion
- [X] T071 [US5] Element types `booster_scene`, `booster_look`, `booster_opening`, `card_reveal`, `card_face`, `card_back` in `modules/visuals/manifest.py` and `analysis.py` (payload rules of pack-format.md, durations ≤ 4 s/3 s) (R23)
- [X] T072 [US5] Scene bindings `modules/visuals/scenes.py` + `PUT /admin/visuals/scenes/{booster_key}` and Review step bindings (draft/publish) + `GET /visuals/scenes/{booster_key}`
- [X] T073 [US5] `frontend/src/features/marketplace/boosters/scene/{SceneHost.tsx,parts.ts}`: resolves parts (pack or default), drives phases from `BoosterReveal.tsx` (which keeps drawing cards), renders css/glsl/js parts with context `{phase, rarity, index, count, reducedMotion}` only; default parts extracted from `boosters.css` into the socle (T036)
- [X] T074 [US5] Booster composition elements published through `CatalogWriter` (odds kept by administrators after creation, rule #81) — verify in `modules/marketplace/products/sync.py`; Review step shows pool/odds
- [X] T075 [P] [US5] Example pack `examples/visual-packs/booster-scene/` (booster look, opening, legendary reveal, card back) with its README section

**Checkpoint**: SC-008 holds.

---

## Phase 8: User Story 7 — Packs evolve: updates, versions, rollback, switch off (Priority: P2)

**Goal**: safe updates, rollback, emergency stop, archive/remove/purge.

**Independent Test**: v1 → v2 removing an element; the element leaves the shop, owners keep it; roll back to
v1; switch off/on; remove with owners archives; remove without owners removes.

- [X] T076 [P] [US7] `backend/tests/integration/visuals/test_lifecycle.py`: updates check (mocked GitHub), publish v2 withdraws the dropped element (owners keep it), rollback restores v1 economy and claims (`replaced_from` restored), switch off → files 404 + products off sale + epoch event, archive when owners > 0, removal when 0 (files deleted, tombstone, products retired), purge never-published, socle refused
- [X] T077 [US7] `CatalogWriter.owners(keys)` and `retire(actor, key)` in `backend/src/portalab/capabilities/visuals.py` + `backend/src/portalab/modules/marketplace/products/sync.py` (R21)
- [X] T078 [US7] Lifecycle service `backend/src/portalab/modules/visuals/lifecycle.py`: rollback †, remove † (archive/remove), purge, superseding; claims and interfaces kept consistent in one transaction; audit and events
- [X] T079 [US7] Admin API rollback/remove/purge/updates in `modules/visuals/api/admin.py`
- [X] T080 [US7] Pack actions UI `frontend/src/features/visuals/PackActions.tsx` (switch, rollback picker, remove dialog with owners and archive explanation, purge) and « update available » in `PackList.tsx`
- [X] T081 [US7] Owners' lists show a look whose pack is off as « currently unavailable » (`frontend/src/features/community/profile/ProfileCustomizer.tsx`, appearance page) — `live_looks.held`, the cosmetics reader's `waiting: {unavailable}`, shown to owners only, never put on again until the pack is back

**Checkpoint**: SC-010 holds.

---

## Phase 9: User Story 6 — Packs restyle widgets and bring new ones (Priority: P3)

**Goal**: widget styles from packs; sandboxed widgets fed by declared contracts only.

**Independent Test**: a pack with a widget style and a widget needing `me.progression`: the style applies; the
widget shows the member's own progression only; an undeclared or forbidden contract yields nothing / empty.

- [X] T082 [P] [US6] `frontend/tests/unit/visuals/widget-contracts.test.ts`: projection per contract (only schema fields), forbidden → `{state: "forbidden"}`, undeclared contract never fetched
- [X] T083 [P] [US6] `backend/tests/unit/visuals/test_widget_contracts.py`: analysis refuses unknown contracts; Review requires each contract's acceptance; `GET /admin/visuals/contracts`
- [X] T084 [P] [US6] `frontend/tests/e2e/visual-packs/widgets.spec.ts` (the real Vigie pack and sandbox bootstrap, API stubbed: readable contracts only, settings, line/block forms, an option replacing a Portalab widget, a frame look)
- [X] T085 [US6] `WIDGET_CONTRACTS` catalog in `backend/src/portalab/capabilities/visuals.py` (`me.progression`, `me.watching`, `media.recently_added`, `me.statistics`: permission, refresh, fields, plain-words description) + `GET /admin/visuals/contracts` (R26)
- [X] T086 [US6] Element types `widget`, `widget_style` and `widget_option` (add-ons worn through `_options`, css and/or sandboxed js `replace`/`overlay`; values of a pack widget's own settings) in `manifest.py`/`analysis.py`; `economy.sold: false` offers them to everyone; `widget_style` and `widget_option` published as `widget_option` products; `skins.css` looks extracted to built-in packs (T036) with hook `[data-widget-style="<look>"]` set by the widget frame (`frontend/src/features/dashboard/frame/`) (R25)
- [X] T087 [US6] Contract projections `frontend/src/features/dashboard/contracts/{index.ts,progression.ts,watching.ts,recentlyAdded.ts,statistics.ts,widgetData.ts}` (zod schemas over the existing query hooks; `widget:<key>`: any dashboard widget's data)
- [X] T088 [US6] `frontend/src/features/dashboard/widgets/pack/{PackFrame,PackWidget,WidgetAddons}.tsx`: sandboxed frame, posts projected data, settings and form (`line|column|block|tall`) per sandbox-protocol.md, empty state; options worn on any widget (`_options`) and frame looks (`_skin`) chosen in the widget's settings; data needs listed in the widget catalog (`catalog/CatalogDrawer.tsx`)
- [X] T089 [P] [US6] Example pack `examples/visual-packs/widgets/` (a widget style + a progression widget)

**Checkpoint**: SC-009 holds.

---

## Phase 10: User Story 8 — A pack author knows what to write (Priority: P3)

**Goal**: format, contracts, examples and the same analysis offline.

**Independent Test**: following the docs only, an author writes a pack with one element of each kind; the
offline analysis reports no blocking finding; it imports and publishes.

- [X] T090 [P] [US8] `backend/tests/unit/visuals/test_cli_analyse.py`: exit codes 0/1/2, `--json` equals the report the import stores
- [X] T091 [US8] `portalab visuals analyse` and `portalab visuals builtin sync [--dry-run]` in `backend/src/portalab/modules/visuals/cli.py`, registered in `backend/src/portalab/app/cli.py` (R32)
- [X] T092 [US8] `docs/visual-packs.md`: format, every element type's contract with an example, sandbox protocol, analysis codes, workflow; `examples/visual-packs/README.md` points to it
- [X] T093 [US8] Examples complete: Nordlys and Abysses on the final format, plus booster-scene (T075) and widgets (T089); `backend/tests/unit/visuals/test_examples.py` analyses each with 0 blocking finding

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T094 [P] Isolation campaign `frontend/tests/e2e/visual-packs/isolation.spec.ts` with test-only probe elements in `frontend/tests/fixtures/visual-probes/` (each attempts one forbidden capability — cookies, storage, network, parent DOM, top navigation, popup, form, protected surface by CSS — and reports through the sandbox channel); all must report « refused » (R33, SC-004)
- [ ] T095 [P] `backend/tests/security/visuals/test_archives.py`: malformed archives (T003 generators) store nothing; GitHub redirects off-host stop the import
- [ ] T096 [P] `data-protected` coverage test `frontend/tests/unit/visuals/protected-surfaces.test.tsx` (administration frame, dialogs, purchase sheet, booster confirmation, security pages, sign-in) (R16)
- [X] T097 [P] Regenerate `backend/openapi.json` and `frontend/src/api/generated/schema.ts` (`npm run gen:api && npm run check:api-drift`)
- [ ] T098 [P] Accessibility sweep (axe) of the workflow pages and pack navigation at 3 widths in `frontend/tests/a11y/visual-packs.spec.ts`
- [ ] T099 Bundle size check: main chunk smaller than before the extraction (record both in `specs/028-visual-packs/quickstart.md`)
- [ ] T100 Full gates (backend pytest/ruff/mypy/lint-imports; frontend lint/typecheck/test/build/check-tokens/i18n:check) and quickstart scenarios 1–9 run on the POC instance (8444) then on the LAN after redeploy

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1** (workflow) depends on Phase 2 only. **US3** (security) depends on Phase 2 only (T012 for the
  sandbox route) and can run in parallel with US1.
- **US2** (built-in packs) depends on US1's publish path (T021) and on T038 (renderer kind); T043 (removing
  code) only after T031–T033 are green.
- **US4** depends on Phase 2 (sandbox) and T037 (built-in navigations as `renderer`).
- **US5** and **US6** depend on US1 (Review step) and on T036 (default parts / widget styles extracted).
- **US7** depends on US1 (publish) and T041 (state API).
- **US8** depends on the final format (US5, US6 types).
- **Polish** last.

## Parallel Opportunities

- Phase 1: T002, T003, T004 together.
- Phase 2: T006 with T007; T015, T016, T017 together once T008 exists.
- US1 tests T018–T020 together; T025 and T030 beside the backend work.
- US3 tests T047–T051 together; T052–T057 (app/surface) beside T058–T061 (guard).
- US5 T075 and US6 T089 (examples) beside their implementation.
- Polish T094–T098 together.

## Implementation Strategy

1. **MVP** = Phases 1–3 (registry + workflow) **and** Phase 5 (security): the POC becomes durable and the
   portal closes to visitors — shippable on its own.
2. Then US2 (built-in packs): the largest move, guarded by the frozen fixture; land the extraction in one
   commit with the parity tests green before deleting code.
3. Then US7, US4, US5 (P2), then US6, US8 (P3), then polish.
4. One implementation commit for the spec on its `impl/028-visual-packs` branch (project workflow), from
   this branch.
