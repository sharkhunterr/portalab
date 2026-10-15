# Implementation Plan: Visual Packs (Every Look as a Pack, Visual Import Workflow, Pack Navigations, Booster Scenes, Widgets, Minimal Public Surface)

**Branch**: `028-visual-packs` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/028-visual-packs/spec.md`

## Summary

Turn the proof of concept of issue #1 (branch `poc/visual-packs`) into the product. A new module `visuals`
(schema `visuals`) owns the pack registry in PostgreSQL (packs, versions, elements, look claims, scene
bindings), the six-step import workflow (Import → Analysis → Security → Test → Review → Validation) with
versions, rollback, switch off, archive/remove/purge, and publication through Marketplace's
`catalog_writer`. Every built-in look — about 1 200 visual products, 52 interfaces and ~26 000 lines of look
CSS/GLSL — is extracted into pack folders shipped with the image (`packs/builtin/`: an always-on socle,
universe/season/HD sub-packs, a base collection), synced at start-up, the first run adopting existing
products so owners notice nothing. Renderers stay in the portal (CSS guard, GLSL runners, parametric
renderers, sandboxed scripts); looks become data. Packs gain navigations of their own (POC), booster scenes
(parts drawn around the portal's own cards) and widgets (styles, and sandboxed widgets fed by declared data
contracts). Security closes the portal to visitors: without a session only signing in answers, health only
from local networks, the sandbox and pack files need a session, and the intrusion guard's blocks are
persisted, alerting through events and liftable from the server console.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 on Node 22 (frontend)
**Primary Dependencies**: existing FastAPI/Pydantic 2/SQLAlchemy 2 async/Alembic/httpx/Typer; React 19,
TanStack Query, React Router, Radix UI, Tailwind on tokens, react-intl, zod. **No new dependency** (the POC
needed none: zip reading via `zipfile`, GitHub via `httpx`, CSS via the browser's CSSOM).
**Storage**: PostgreSQL — new schema `visuals` (`packs`, `pack_versions`, `elements`, `look_claims`,
`scene_bindings`, `registry_epoch`), new table `identity.security_blocks`; pack files on disk under
`DATA_DIR/visuals/store/<pack>/<sha256>/` (immutable); built-in packs in the image at `/app/packs/builtin`.
**Testing**: pytest (unit/integration/migrations/contract/security), Vitest + Testing Library, Playwright
(e2e: workflow, navigation, booster scene, widgets, isolation, anonymous surface)
**Target Platform**: self-hosted Linux container (single image `serve`/`worker`); evergreen browsers on phone,
tablet, desktop
**Project Type**: web application (backend modules + SPA)
**Performance Goals**: `GET /visuals/active` ≤ 60 kB gzip, served from memory (epoch cache) in < 20 ms;
pack files immutable-cached; switch off visible to members ≤ 1 min (SC-010); a failing script replaced ≤ 5 s
(SC-007); main JS bundle smaller than today (look code leaves it); import + analysis of a 20 MB pack < 10 s
**Constraints**: no anonymous route beyond FR-036; pack content never trusted (sandbox, CSS guard, inert
files); keys, owners, equipped looks and preferences preserved byte-for-byte by the migration; `visuals.manage`
reserved to the Admin; reduced motion and protected surfaces always win; Docker image size (built-in packs
≈ 15 MB of text/fonts).
**Scale/Scope**: ~40 built-in packs, ~1 300 elements; tens of imported packs; registry changes rare (admin
actions); ≤ a few hundred members.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] I. Product Integrity — PASS: no business rule changes; the economy of built-in products is adopted as is (R7); contradictions (Admin blocked by the guard, removal with owners) surfaced and clarified in the spec.
- [x] II. Modular Architecture — PASS: new module `visuals` uses capabilities (`marketplace.catalog_writer`, `ui` theme registry, `WIDGET_CONTRACTS`); no cross-module imports; guard moves into `identity` (owner of sessions).
- [x] III. Extensibility First — PASS: packs are the extension point for looks; the core works with the socle only; disabling a pack keeps ownerships and preferences (looks fall back, come back).
- [x] IV. Event-Driven Domain — PASS: `visuals.changed`, `visuals.pack.*`, `security.block.started`, `security.blocks.changed` through the outbox; alerts are event consumers (R31).
- [x] V. Source of Truth & Data Integrity — PASS: registry in PostgreSQL, files immutable by fingerprint, removal keeps tombstones and catalog history; migration verified against a frozen fixture.
- [x] VI. Security & Authorization — PASS: server-side default deny extended to « no session ⇒ nothing » (R27); reserved permission (R17); confirmations on sensitive actions; sandbox + CSP + CSS guard + inert files; audit of every pack action.
- [x] VII. Privacy by Design — PASS: widgets receive only the viewer's own data through contracts within their permissions; pack scripts never see the session.
- [x] VIII. Testability & Quality — PASS: SC-001…SC-010 mapped to automated suites (quickstart), including an isolation campaign and an anonymous sweep.
- [x] IX. Resilience & Graceful Degradation — PASS: a failing look/navigation/scene/widget falls back to the default; a pack off never breaks a page; the guard's failure never fails a request.
- [x] X. UX Consistency — PASS: workflow built with the page kit (PageHeader, Card, stepper from the design system); every step states where/what/next.
- [x] XI. Functional State vs Presentation — PASS: scenes draw around the portal's draw (R23); themes and packs never change rules; accessibility preferences win.
- [x] XII. Accessibility — PASS: pack navigations keep landmark/skip link/keyboard; reduced motion honoured by every moment; workflow usable on phone.
- [x] XIII. Observability & Auditability — PASS: every pack action and block audited with actor (console included); element failures reported and counted.
- [x] XIV. Deterministic Business Rules — PASS: booster draw unchanged; look claims deterministic; rollback reuses recorded decisions.
- [x] XV. Internal Economy Integrity — PASS: products published through the Marketplace path; removal never deletes products or transactions.
- [x] XVI. AI Safety & Boundaries — N/A.
- [x] XVII. Search and AI Independence — N/A.
- [x] XVIII. Configuration Hierarchy — PASS: guard thresholds, health networks, limits are global settings with safe defaults; trusted proxies is a bootstrap setting.
- [x] XIX. Versioning & Evolution — PASS: POC registry imported; `format: 1` packs stay valid; theme v2 unchanged; existing products, preferences and themes keep their keys.
- [x] XX. Simplicity & Maintainability — PASS: no new dependency; one format for built-in and outside looks; one analysis (also the CLI); POC code reused, not rewritten.

Post-design re-check (after Phase 1): unchanged — all PASS; no Complexity Tracking entry.

## Project Structure

### Documentation (this feature)

```text
specs/028-visual-packs/
├── plan.md
├── research.md          # R1–R35
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-contracts.md
│   ├── pack-format.md
│   ├── sandbox-protocol.md
│   ├── cli-contracts.md
│   └── ui-contracts.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
packs/builtin/                                   # NEW built-in packs (R5), copied to /app/packs/builtin
├── portalab-socle/                              # default interfaces, free looks, built-in navigations (renderer)
├── portalab-base/                               # the « base collection »
├── portalab-<universe>/ …                       # one per universe (cosmos, upside-down, middle-earth, …)
├── portalab-season-<season>/ …                  # valentine, spring, summer, halloween, christmas
└── portalab-hd-<collection>/ …                  # HD collections (level-ups HD, …)

backend/src/portalab/
├── capabilities/visuals.py                      # live_looks, CatalogWriter (+owners, retire), WIDGET_CONTRACTS
├── capabilities/themes.py                       # built-in look tuples removed after extraction (R8)
├── modules/visuals/                             # NEW module (from modules/ui/visuals + ui/api/visuals.py)
│   ├── module.py                                # wiring, permissions, events, settings
│   ├── models/__init__.py                       # SQLAlchemy models (data-model.md)
│   ├── manifest.py, analysis.py, store.py, github.py, sandbox.py   # POC, completed
│   ├── registry.py                              # repository over visuals.* (replaces state.json)
│   ├── workflow.py                              # steps, measures, draft, publish/refuse
│   ├── lifecycle.py                             # state, rollback, archive/remove/purge, claims
│   ├── builtin.py                               # built-in sync + first-run adoption (R6, R7)
│   ├── scenes.py                                # scene bindings
│   ├── cache.py                                 # epoch cache (active manifest, vocabulary)
│   ├── cli.py                                   # `visuals analyse`, `visuals builtin sync`
│   └── api/{members.py, admin.py}
├── modules/identity/guard/                      # intrusion guard (from app/intrusion.py), blocks table, CLI
├── modules/marketplace/products/sync.py         # owners(), retire()
├── modules/ui/                                  # themes registry stays; builtin/*.json move to packs
├── app/security.py                              # ANONYMOUS_ROUTES allow-list, generic 401, health networks
├── app/spa.py                                   # public-assets gate (R27), /packs/socle
├── app/demo_shop.py                             # visual entries removed (moved to packs); functional products kept
└── migrations/{visuals/versions/…_visuals_0001.py, identity/versions/…_security_blocks.py}

backend/tests/
├── unit/visuals/ …                              # manifest, analysis, css rules, claims, workflow states
├── integration/visuals/ …                       # workflow, lifecycle, builtin sync, scenes, files, reports
├── integration/identity/test_guard.py           # persisted blocks, console, alerts
├── migrations/test_visuals_0001.py
├── security/test_anonymous_surface.py, security/visuals/ …
└── fixtures/visual-packs/ …                     # blocking, malformed, probes (test-only)

frontend/src/
├── design-system/visuals/                       # from themes/external: registry client, cssGuard, sandbox,
│   │                                            #   renderers (css, glsl, js, renderer), resolveLook
├── design-system/themes/…                       # look CSS/GLSL removed after extraction; runners kept
├── features/visuals/                            # admin: PackList, VersionWorkflow, steps/*, TestStage
├── features/security/SecurityBlocks.tsx
├── features/marketplace/boosters/scene/         # SceneHost, parts resolution, default scene parts
├── features/dashboard/widgets/pack/             # PackWidget host; contracts/ (zod projections)
├── shell/nav/PackNav.tsx                        # POC, hardened (heartbeat, fallback)
└── scripts/extract-builtin-packs.mjs            # one-off extraction (R8), removed after the move
frontend/tests/{unit/visuals, e2e/visual-packs}/
tests/fixtures/builtin-looks-before.json         # frozen keys before the move (R8)
docs/visual-packs.md · examples/visual-packs/{nordlys,abysses,booster-scene,widgets}/
```

**Structure Decision**: existing web-application layout. Backend: one new module (`visuals`) taking over the
POC code under `ui`, the guard moved into `identity`, small additions to Marketplace (`owners`, `retire`) and
`app/` (anonymous allow-list, SPA gate). Frontend: the POC's `themes/external` becomes
`design-system/visuals`; the admin page becomes a stepper; booster and dashboard gain pack hosts. Built-in
looks leave the code for `packs/builtin/`, with a frozen fixture proving nothing was lost.

## Delivery slices (for /speckit.tasks)

1. **Foundation**: module `visuals`, schema + migration (POC state import), registry repository, epoch cache
   and `visuals.changed`, reserved `visuals.manage`, inert file serving, session-only sandbox, POC code moved
   (`ui/visuals` → `visuals`, `themes/external` → `design-system/visuals`).
2. **US3 Security** (P1): anonymous allow-list + generic 401 + SPA gate, health networks + trusted proxies,
   first-run closed, terms after sign-in, #134 port, guard persisted in `identity` + settings + events +
   console CLI.
3. **US1 Workflow** (P1): steps on the version, measures, draft, confirmations, publish/refuse with claims;
   admin stepper UI and test stage.
4. **US2 Built-in catalog** (P1): fixture of keys, extraction script, `packs/builtin/*`, built-in sync and
   first-run adoption, removal of look code, demo seed/first-run choices.
5. **US7 Lifecycle** (P2): updates, rollback with claims, switch, archive/remove/purge, element health.
6. **US4 Navigations** (P2): heartbeat/fallback hardening, protected admin navigation, e2e on 3 widths.
7. **US5 Booster scenes** (P2): part types, analysis, bindings, SceneHost around `BoosterReveal`, example.
8. **US6 Widgets** (P3): widget styles from packs, contracts catalog, PackWidget host, example.
9. **US8 Authoring** (P3) and polish: CLI analyse, docs, examples, isolation campaign, OpenAPI/client
   regeneration, a11y sweep.

## Complexity Tracking

No constitution violations — section intentionally empty.
