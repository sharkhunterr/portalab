# Tasks: Trusted Interfaces (Complete Interfaces by Packs, Trust Layer, Broker, Hardened Looks)

> **Scope revision 2026-10-17** — reduced to the exposure catalog, the « Interfaces » gallery, safe mode and fixes; complete interfaces, trust layer, seal, hardened looks and pack origin dropped, budget postponed. See [SCOPE-REVISION.md](SCOPE-REVISION.md).

**Input**: Design documents from `/specs/029-trusted-interfaces/` (plan.md, spec.md, research.md R1–R20,
data-model.md, contracts/, quickstart.md)
**Prerequisites**: spec 028 as built (`impl/028-visual-packs`): `modules/visuals`, `design-system/visuals`,
the sandbox bootstrap, `/visuals/live/{epoch}`, `PROTECTED_PAGES`, the isolation campaign.
**Tests**: requested — every success criterion maps to a suite (quickstart.md).
**Implementation branch**: `impl/029-trusted-interfaces` from `impl/028-visual-packs` (POC worktree); paths
below are relative to the application folder `portalab/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Create `impl/029-trusted-interfaces` from `impl/028-visual-packs` in the POC worktree and copy the planning documents `specs/029-trusted-interfaces/` from branch `029-trusted-interfaces` (no merge)
- [X] T002 [P] Bootstrap settings `pack_origin_port` (default `bind_port + 1`, env `PACK_ORIGIN_PORT`) and `pack_origin_url` (optional, env `PACK_ORIGIN_URL`) in `backend/src/portalab/core/settings.py`, documented in `deploy/` env examples
- [X] T003 [P] Seal assets: the 48 seal symbols (icon names from the existing icon set) and 12 fixed colours (contrast ≥ 4.5 on light and dark) in `frontend/src/trust/seal.ts`, mirrored as bounds in `backend/src/portalab/modules/identity/seal/constants.py`

## Phase 2: Foundational (blocking)

- [X] T004 Exposure capability `backend/src/portalab/capabilities/exposure.py`: `Exposure` (read/action/committing/forbidden), `OperationLabel`, `ComponentLabel`, `ExposureRegistry` (declare, resolve(method, path) with forbidden prefixes first, unlabelled ⇒ forbidden, `read` only on GET, `committing` needs confirm words), `FORBIDDEN_PREFIXES` per contracts/exposure-catalog.md
- [X] T005 [P] Module label tables (data only) declaring v1 exposable operations: `modules/media/exposure.py` (library, items, search, requests list, request create = committing, favourites/watchlist = action, images via host), `modules/community/exposure.py` (members directory read, feed read, posts/comments create = committing, reactions = action), `modules/dashboard/exposure.py` (dashboard read), `modules/marketplace/exposure.py` (catalog/product reads, purchases list, purchase = committing, booster open = committing, reserve read), `modules/gamification/exposure.py` (progression, achievements, quests, leaderboards reads), `modules/notifications/exposure.py` (list read, mark read = action, topics `notifications.*`), `modules/content/exposure.py` (news, wiki, calendar reads), `modules/search/exposure.py` (search read); host components `media.player`, `media.reader`, `community.avatar`, `marketplace.booster`; wiring in `backend/src/portalab/app/wiring.py`
- [X] T006 [P] Test `backend/tests/unit/test_exposure_catalog.py`: every route of the application resolves to a label; forbidden prefixes never exposed whatever a module declares; GET never action/committing; non-GET never read; committing labels carry en/fr confirm words; the resolved table printed on failure
- [X] T007 `GET /api/v1/exposure` (members) in `backend/src/portalab/app/exposure_api.py` listing non-forbidden operations and components with words and topics (ETag per release); route itself forbidden to interfaces
- [X] T008 Seal: model + migration `backend/migrations/identity/versions/…_identity_seals.py` (`identity.seals` per data-model.md, FK cascade in migration only), service (`get_or_assign` random, `choose` validated), routes `GET/PUT /api/v1/me/seal` in `backend/src/portalab/modules/identity/seal/`, audit `identity.seal.changed` (no value), privacy contributor (export + deletion)
- [X] T009 [P] Test `backend/tests/integration/identity/test_seal.py`: assigned at random once, kept; choose validates symbol/colour/word; other members never read it; exported and deleted with the account
- [X] T010 Pack origin: `backend/src/portalab/app/pack_origin.py` ASGI app serving `/sandbox/script` and `/sandbox/app` (bootstrap documents of `modules/visuals/sandbox.py`, CSP per kind per research R1/R2, `frame-ancestors <main origin>`, `Origin-Agent-Cluster: ?1`, `Cross-Origin-Resource-Policy: cross-origin`, `Cache-Control: no-cache`); `portalab serve` runs it on `pack_origin_port` beside the main app (two `uvicorn.Server` in one loop, same TLS) in `backend/src/portalab/app/cli.py`
- [X] T011 Main CSP `frame-src` gains the pack origin; `GET /api/v1/ui/runtime` (or the existing bootstrap config route) exposes `packOrigin` to the SPA in `backend/src/portalab/app/security.py` and the config route
- [X] T012 [P] Test `backend/tests/unit/visuals/test_pack_origin.py`: only the two documents answer (everything else 404), headers and policies per kind, no route of the API mounted, no cookie read
- [X] T013 Frontend sandbox frames load from the pack origin (`packOrigin` + `/sandbox/script`), the 028 member route `/api/v1/visuals/sandbox` kept as fallback when no pack origin is configured, in `frontend/src/design-system/visuals/sandbox.ts`; e2e support serves both documents in `frontend/tests/e2e/visual-packs/support.ts`
- [X] T014 Setting `ui.interfaceApp` (user scope, `{desktop, tablet, phone}`) in `backend/src/portalab/modules/ui/settings.py` with its validator (live `interface_app` look, owned when sold) and `LOOK_TYPES["interface_app"] = "app"` in `backend/src/portalab/capabilities/visuals.py`

**Checkpoint**: catalog resolves every route, seal exists, pack origin serves sandbox documents.

## Phase 3: User Story 1 — Genuine confirmations and a way back (P1) 🎯 MVP

**Goal**: every committing confirmation is Portalab's (top layer, shadow root) with the member's seal;
an exit control, a shortcut and a safe mode; protected pages carry no pack content.
**Independent test**: an imitation without seal vs the genuine confirmation with it; exit < 1 s; `?safe=1`
loads no pack content.

- [X] T015 [P] [US1] Unit tests `frontend/tests/unit/trust/trust-layer.test.tsx`: `confirmTrusted` opens a modal dialog inside `<portalab-trust>`'s shadow root, shows words/content/free text/amount/seal, resolves true/false, Escape cancels, focus trapped and restored; document stylesheets (pack sheets) do not reach it
- [X] T016 [P] [US1] Unit tests `frontend/tests/unit/trust/safe-mode.test.tsx`: `?safe=1` and the switch set/clear `portalab.safe`; in safe mode no `ExternalVisualsLoader`, no interface host, no pack palette; the banner leaves it
- [X] T017 [US1] `<portalab-trust>` custom element + React portal into its shadow root with its own constructed stylesheet in `frontend/src/trust/TrustLayer.tsx`, mounted once by `frontend/src/main.tsx`; `confirmTrusted()` in `frontend/src/trust/confirm.ts`; seal drawing `frontend/src/trust/Seal.tsx` (reads `/me/seal`, cached)
- [X] T018 [US1] Portalab's committing flows go through `confirmTrusted`: purchase (`features/marketplace/product/ProductSheet.tsx` replaces its inline confirmation), paid booster opening (`features/marketplace/boosters/BoosterReveal.tsx`), media request (`features/media/…` request action), deletions and publications of community posts/comments and tickets (their delete/publish actions), account deletion (account page); i18n keys in `backend/locales/{en,fr}/trust.json` — *built: the six committing operations of the catalog (purchase, funding, vote, proposal publication, media request and its cancellation) + paid booster + account deletion; there are no community posts/comments in the code and tickets are not exposable; keys under `core:trust.*` and each module's namespace*
- [X] T019 [US1] Seal picker on the account page `frontend/src/features/account/SealPicker.tsx` (48 symbols × 12 colours, word, preview of a confirmation, explanation) — *native radio inputs*
- [X] T020 [US1] Exit control (`popover="manual"`, re-shown after dialogs) and Alt+Shift+P in `frontend/src/trust/ExitControl.tsx` (*built inside `TrustLayer.tsx`; a navigation taken back is restarted folded*); shown while an interface app or a full-screen pack navigation is active; the sandbox bootstrap registers a capture-phase key listener before the pack's module and posts `exit` (`backend/src/portalab/modules/visuals/sandbox.py`)
- [X] T021 [US1] Safe mode in `frontend/src/trust/safeMode.ts` + banner in `frontend/src/trust/SafeModeBanner.tsx` (*built inside `TrustLayer.tsx`, a top-layer popover; switch in `features/appearance/SafeModeSwitch.tsx`*); AppShell skips `ExternalVisualsLoader`, the interface host and pack palettes when on; appearance page switch
- [X] T022 [US1] Protected pages withdraw every pack stylesheet (registry scope flag in `frontend/src/design-system/visuals/registry.ts`) and suspend the interface host while on `PROTECTED_PAGES` (`frontend/src/shell/AppShell.tsx`)
- [X] T023 [US1] E2E `frontend/tests/e2e/trust/confirmations.spec.ts`: purchase, booster, request, deletion each show the seal in the top layer; a page-drawn imitation shows none; `frontend/tests/e2e/trust/exit-and-safe-mode.spec.ts`: exit control and shortcut < 1 s, `?safe=1` loads no pack request

**Checkpoint**: US1 independently testable (MVP).

## Phase 4: User Story 2 — Looks no longer escape or mislead (P1)

**Goal**: hardening rules at analysis and in the guard, confinement CSS, looks shielded from Portalab's words.
**Independent test**: probe looks are refused/neutralised; built-in packs and examples still pass.

- [X] T024 [P] [US2] Tests `backend/tests/unit/visuals/test_hardening.py`: `position: fixed|sticky`, `z-index` outside −1…10, viewport units in sizes/offsets, `content` with letters/digits ⇒ blocking with plain words; symbols/emoji/`attr()`/`counter()`/empty content allowed
- [X] T025 [P] [US2] Tests in `frontend/tests/unit/visuals/css-guard.test.ts`: the guard drops the same declarations at run time; look sheets are shielded from `[data-protected]`
- [X] T026 [US2] Analysis rules (CSS declarations parsed per rule) in `backend/src/portalab/modules/visuals/analysis.py` (`css.escape`, `css.stacking`, `css.viewport`, `css.text` findings with plain words in `backend/locales/{en,fr}/admin.json`) — *plus `css.confinement` (info): what a look says about overflow/isolation/containment on its own element is left out; full-screen layers (level-up, effect, ambient, profile background, booster backdrop/opening) may use viewport units*
- [X] T027 [US2] Guard neutralisation and look shielding in `frontend/src/design-system/visuals/cssGuard.ts` (drop declarations; `shieldSelector` applied to look sheets) — *looks are shielded from `[data-protected="text"]` (Portalab's words) inside `:where()` (no specificity change); interfaces keep the broad `[data-protected]` shield; confinement declarations on a look's own element dropped*
- [X] T028 [US2] Confinement in Portalab's base CSS: `isolation: isolate` on every look hook element, `overflow: clip; overflow-clip-margin: 24px` on small hooks (avatar frame, level badge, name, title, badge, notification, widget frame, card face/back) in `frontend/src/design-system/themes/cosmetics.css` and the relevant base sheets; computed-style parity re-checked on the built-in looks — *booster cards excluded from the clip (their hook also carries Portalab's own effects; they live on the full-screen booster stage); the notifications' region clipped at 4rem (looks place a chat head or a bottle beside a toast)*
- [X] T029 [US2] `data-protected` on Portalab's words: prices (`ProductCard`, `ProductSheet`), rarities (`RarityTag`), booster card results, amounts (coins/XP badges), identity and security indications in `frontend/src/features/…` and `design-system/components/Badges.tsx` — *as `data-protected="text"` (a word, not a surface); the level digit inside a level badge stays the badge look's; known limit: a look may still redefine Portalab's custom properties on its own element (e.g. a rarity's tone colour) — the words themselves stay Portalab's*
- [X] T030 [US2] Adapt built-in packs that the new rules refuse (`packs/builtin/**/look.css`), restamp (`backend/scripts/stamp_builtin_packs.py`); `backend/tests/unit/visuals/test_builtin_packs.py` keeps every built-in pack free of blocking findings
- [X] T031 [US2] Published versions re-analysed at start for the new rules: findings « to update » shown on the pack (never blocking what is published) in `backend/src/portalab/modules/visuals/builtin.py`/`service.py` and `frontend/src/features/visuals/VisualsAdmin.tsx`
- [X] T032 [US2] Isolation probes for looks (escape the box, rise above a confirmation, replace a rarity's text) added to `frontend/tests/fixtures/visual-probes/` and asserted in `frontend/tests/e2e/visual-packs/isolation.spec.ts`

**Checkpoint**: US2 independently testable.

## Phase 5: User Story 3 — A completely different interface (P1)

**Goal**: `interface_app` elements run full-screen from the pack origin, work through the broker, are chosen by
members, fall back on failure.
**Independent test**: Teletext published, chosen, browsed (same reads as Portalab), a request confirmed with
the seal, frozen ⇒ Portalab back < 5 s.

- [X] T033 [P] [US3] Tests `backend/tests/unit/visuals/test_interface_app.py`: manifest `interface_app` block, analysis findings per research R16 (unknown/forbidden/unlabelled operation or component, forms, light, phone warning), size limits
- [X] T034 [P] [US3] Tests `frontend/tests/unit/visuals/broker.test.ts`: declared ∧ accepted ∧ not forbidden; committing waits for `confirmTrusted`; header `X-Portalab-Interface`; image addresses replaced by assets; problems mapped; subscribe forwards declared topics only
- [X] T035 [US3] Manifest + analysis for `interface_app` (type, `app` block, limits 60 MB/20 MB) in `backend/src/portalab/modules/visuals/manifest.py`, `analysis.py`, `store.py`; claims and vocabulary (`live_looks`) include it — *the store reads up to 60 MB / 20 MB a file; the analysis keeps a pack of looks within 20 MB / 5 MB (`pack.too_large`, `file.too_large`); `.wasm`/`.bin` files accepted; offered by default (`economy.sold: false` giveable)*
- [X] T036 [US3] Bootstrap app mode in `backend/src/portalab/modules/visuals/sandbox.py`: `api.call`, `api.subscribe`, `api.place`, `api.onQuality`, `health` every 2 s (rAF cadence, `performance.memory`), `texts` walker on demand, `exit` shortcut; CSP per kind (R2)
- [X] T037 [US3] Broker `frontend/src/design-system/visuals/broker.ts` (checks, confirmation, fetch with session and header, scrubbing to assets, problems, subscriptions over `connectStream`) — *a committing call's confirmation shows what Portalab reads of it (a product's name and price, a project's or proposal's title, a title's name by its id or TMDB id), never the interface's words; path values may not climb (`.`/`..` refused); 40 calls per 10 s*
- [X] T038 [US3] Interface host `frontend/src/design-system/visuals/interfaceHost.tsx`: full-screen frame from the pack origin below the trust layer, `run` with source + context (form, language, reduced motion, text scale, colour scheme, page, equivalents), context updates, equivalents ⇄ addresses (R19), heartbeat (028) ⇒ fallback ≤ 5 s with a notice and a report; mounted by `frontend/src/shell/AppShell.tsx` when the member's choice for the current form is set and not in safe mode/protected page — *portalled to `body`, Portalab's `#root` made inert while it shows; heartbeat every 1 s, 3 silences (back < 5 s); navigations at most every 100 ms, the last one kept; components drawn by a registry US5 fills*
- [X] T039 [US3] `GET /api/v1/visuals/interfaces` (members: live interfaces with preview, forms, read words, locked/waiting) in `backend/src/portalab/modules/visuals/interfaces.py` + `api/routes.py`; choice validation for `ui.interfaceApp`
- [X] T040 [US3] Appearance « Complete interfaces » picker `frontend/src/features/appearance/InterfacePicker.tsx` (Portalab's first, per form, preview, reads, owned/price)
- [X] T041 [US3] Example pack `examples/visual-packs/teletext/` (pages 100 index, 200 library, 300 progression, 400 shop, 500 notifications; title request; equivalents; phone/tablet/desktop; light version) passing analysis
- [X] T042 [US3] Integration tests `backend/tests/integration/visuals/test_interfaces.py`: import/review/publish Teletext; listing for members; choice saved per form; switched off ⇒ choice kept, Portalab shown
- [X] T043 [US3] E2E `frontend/tests/e2e/interfaces/teletext.spec.ts`: choose, browse pages 100–500, compare reads with Portalab's pages (SC-009), request a title confirmed with the seal, freeze ⇒ back ≤ 5 s (SC-004) — *`frozen.spec.ts` runs with `--site-per-process` (browsers isolate sites and sandboxed frames by default; Playwright's Chromium starts without it — with it the hung frame cannot hang Portalab's page, even on the same site, the next port)*

**Checkpoint**: US3 independently testable.

## Phase 6: User Story 4 — Operations reviewed and checked (P2)

- [X] T044 [P] [US4] Tests `backend/tests/security/test_interface_requests.py`: header with an undeclared/unaccepted/forbidden operation ⇒ 403 before the route; accepted ⇒ normal answer; rate limits ⇒ 429 then `visuals.interface.misbehaved`; committing audited `interface.operation`
- [X] T045 [US4] Review step: operations and components grouped Reads/Actions/Committing with words, each accepted; draft `operations` stored; publication requires all accepted, in `backend/src/portalab/modules/visuals/service.py` and `frontend/src/features/visuals/steps/ReviewStep.tsx` — *as `confirmations.operations` (like 028's data contracts): publication lists each one missing; a trusted (built-in) publication accepts what is declared; the live element carries `accepted`*
- [X] T046 [US4] Middleware `backend/src/portalab/app/interfaces.py` (accepted operations per live element from the registry epoch cache, template matching, rate limits, audit, event) — *`InterfaceGuard`, inside the security layer: unknown/malformed subject, not accepted or forbidden ⇒ 403 before the route; 60 calls / 10 s per member and interface ⇒ 429; 5 refusals in a minute ⇒ `visuals.interface_misbehaved` (once per 10 min) and audit; images named by Portalab's own answers are fetched without the header*
- [X] T047 [US4] Broker refusal for undeclared operations without any request (`ui.interface_operation_refused`) covered in `frontend/tests/unit/visuals/broker.test.ts`

## Phase 7: User Story 5 — Host components (P2)

- [X] T048 [P] [US5] Tests `frontend/tests/unit/visuals/host-components.test.tsx`: place/move/unplace clamp to the viewport, only declared ∧ accepted components, props validated, booster result posted only after reveal
- [X] T049 [US5] Host components layer in `frontend/src/design-system/visuals/hostComponents.tsx`: `media.player` (VideoPlayer), `media.reader` (reader), `community.avatar` (framed avatar), `marketplace.booster` (StageHost, `booster.revealed` event) — *in `frontend/src/features/interfaces/hostComponents.tsx` (the design system does not import features), registered into the host; the player and the reader loaded only when placed; regions clamped to the screen and their content contained; `BoosterReveal` dispatches `portalab:booster-revealed` once every card is shown*
- [X] T050 [US5] Teletext places the player on a title page; E2E `frontend/tests/e2e/interfaces/host-components.spec.ts`: the video plays in the region, the frame never receives a stream address

## Phase 8: User Story 6 — Budgets (P2)

- [X] T051 [P] [US6] Tests `frontend/tests/unit/visuals/budget.test.ts`: under target 3 s ⇒ quality low; 10 s or memory over or no heartbeat ⇒ fallback + report `budget`; reduced motion ⇒ still/light
- [X] T052 [US6] `frontend/src/design-system/visuals/budget.ts` (per-form budgets, health intake from sandboxes and `badgeFx` frame timing, quality messages, fallback, notice via the trust layer); reports reason `budget`/`misbehaved` accepted by `backend/src/portalab/modules/visuals/api/routes.py` — *an interface's health from its frame (every 2 s); the GPU looks measured by what drawing the imported ones costs per frame (the loop itself is capped by the motion setting); an interface over budget gives way to its light version when live, else Portalab's; a GPU look to its CSS version*
- [X] T053 [US6] Heavy probe pack `frontend/tests/fixtures/visual-probes/heavy/` and E2E `frontend/tests/e2e/interfaces/budget.spec.ts` (lowering ≤ 3 s, fallback ≤ 10 s, exit control answers < 100 ms meanwhile)

## Phase 9: User Story 7 — Authoring (P3)

- [X] T054 [P] [US7] `sdk/interface/`: `scripts/gen-interface-sdk.mjs` (frontend `npm run gen:interface-sdk`) generating `portalab-interface.d.ts` from `/exposure` + `backend/openapi.json`; `simulator.js` (sample data for every labelled read, actions recorded, confirmations simulated); `template/` (pack.json, element.json, app.js, run page) — *also `catalog.json` and `samples.json`; the run page is `sdk/interface/run.html` (a pack may not hold an .html file); e2e `tests/e2e/interfaces/sdk.spec.ts` runs the template with the simulator*
- [X] T055 [US7] Offline analysis covers `interface_app` (`backend/src/portalab/modules/visuals/cli.py`), documented in `docs/visual-packs.md` (« Complete interfaces » chapter: protocol, operations, components, limits, SDK)
- [X] T056 [US7] Test step for `interface_app` in `frontend/src/features/visuals/steps/TestStep.tsx`: two profiles (1280×800, 390×844) with the simulator, ready time, fps, memory, probes (exit control hit-test, texts listed, undeclared calls), saved through the measures endpoint — *its reads answered by Portalab for real (the administrator's own, without the interface header: the version is not live), its actions only recorded, never sent; the frames shown small (zoom) but drawn at their real size; actions and refusals listed*
- [X] T057 [US7] Unit test `frontend/tests/unit/visuals/test-step-app.test.tsx` for the measures and probes shape

## Phase 10: Polish & Cross-Cutting

- [X] T058 [P] Isolation campaign extended `frontend/tests/e2e/interfaces/isolation.spec.ts` + probes in `frontend/tests/fixtures/visual-probes/`: imitate a confirmation, read the seal, call undeclared/forbidden operations, cover the exit control, reach the network from an app frame (SC-001)
- [X] T059 [P] Accessibility: axe on the trust dialog, seal picker, interface picker (`frontend/tests/e2e/trust/a11y.spec.ts`)
- [X] T060 OpenAPI + client regeneration (`backend/openapi.json`, `npm run gen:api`), i18n catalogs complete (`npm run i18n:check`)
- [X] T061 Full gates and quickstart scenarios 1–9 on the POC (8444 + pack origin 8445): backend pytest/ruff/mypy/lint-imports; frontend lint/typecheck/test/build/check:api-drift; record results in `specs/029-trusted-interfaces/quickstart.md`

## Dependencies & Execution Order

- Phase 1 → Phase 2 (T004–T014) block every story.
- US1 (Phase 3) first (MVP: the trust layer every later story relies on).
- US2 (Phase 4) independent of US1 except T029 (`data-protected` words) used by US3's confirmations.
- US3 needs Phase 2 (catalog, pack origin, setting) and US1 (`confirmTrusted`, exit control).
- US4 needs US3's element and broker; US5 and US6 need US3's host; US7 needs US3 and US4.
- Polish last.

## Parallel Examples

- Phase 2: T005, T006, T009, T012 in parallel once T004/T008/T010 exist.
- US1: T015, T016 (tests) in parallel; T019 and T021 in parallel after T017.
- US2: T024, T025 in parallel; T028 and T029 in parallel.
- US3: T033, T034 in parallel; T040 and T041 in parallel after T038/T039.

## Implementation Strategy

MVP = Phase 1–3 (the seal and the trust layer on Portalab's own flows, exit and safe mode). Then US2 (closes
#140/#141 for every published pack), US3 (Teletext end to end), US4–US6 (control, components, budgets), US7
and polish. Each phase ends with its tests green and a commit on `impl/029-trusted-interfaces`.
