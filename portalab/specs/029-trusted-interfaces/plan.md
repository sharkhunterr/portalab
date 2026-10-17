# Implementation Plan: Trusted Interfaces (Complete Interfaces by Packs, Trust Layer, Broker, Hardened Looks)

> **Scope revision 2026-10-17** — reduced to the exposure catalog, the « Interfaces » gallery, safe mode and fixes; complete interfaces, trust layer, seal, hardened looks and pack origin dropped, budget postponed. See [SCOPE-REVISION.md](SCOPE-REVISION.md).

**Branch**: `029-trusted-interfaces` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/029-trusted-interfaces/spec.md`

## Summary

Give packs the whole screen without giving them the member. A **trust layer** — a custom element with its own
shadow root, its confirmations in the browser's top layer — draws every committing confirmation (Portalab's own
flows and those an interface asks for) with the exact content and the member's **seal** (a symbol, a colour, a
word kept in `identity.seals`, never handed to a pack), an always-present **exit control** (and Alt+Shift+P),
and a **safe mode**. A new element type **`interface_app`** runs a pack's application full-screen in a frame of a
**separate origin** (a second port serving only static sandbox documents; pack bytes still travel as data) and
works only through a **broker** in Portalab's page, which checks each call against the **exposure catalog**
(every API operation labelled read / action / committing / forbidden by its module; unlabelled = forbidden)
and the operations the Admin accepted at Review — the server checks them again (`X-Portalab-Interface`), rate
limits and audits them. Interfaces place Portalab's own **host components** (player, reader, avatar, booster
stage). 028's looks are **hardened** (no fixed/sticky, bounded stacking, no viewport units, no literal text,
confinement by Portalab's CSS, shielded from Portalab's words); every pack visual runs within a **budget**
with quality lowering and fallback. Authors get an **SDK** (types from the catalog, a simulated broker, a
template), an example **Teletext** interface, and the Test step measures interfaces and runs visual probes.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 on Node 22 (frontend)
**Primary Dependencies**: existing FastAPI/Pydantic 2/SQLAlchemy 2 async/Alembic/uvicorn; React 19, TanStack
Query, React Router, Radix UI, react-intl, zod. **No new dependency** (custom elements, shadow DOM, `<dialog>`,
popover and `postMessage` are platform features; the second port is a second `uvicorn.Server` in the same
process).
**Storage**: PostgreSQL — new table `identity.seals`; 028's `visuals.*` unchanged in shape (the
`interface_app` element in `elements.data`, accepted operations in the version's draft); user setting
`ui.interfaceApp`; browser-local `portalab.safe`.
**Testing**: pytest (unit: exposure catalog over every route, hardening rules, interface analysis; integration:
seal, interfaces registry/choice, server check; security: interface requests, forbidden operations),
Vitest + Testing Library (trust layer, broker, guard, budgets), Playwright (confirmations with seal, exit &
safe mode, Teletext journey with read comparison, host components, budget, isolation campaign extended).
**Target Platform**: self-hosted Linux container (single image `serve`/`worker`), evergreen browsers with
`<dialog>`/popover/top layer (members on older browsers keep Portalab's interface).
**Project Type**: web application (backend modules + SPA).
**Performance Goals**: exit < 1 s (SC-003); failing interface replaced ≤ 5 s (SC-004); trust layer answers
< 100 ms under load (SC-005); Teletext first screen < 3 s on the phone profile, ≥ 30 fps (SC-006); budget
lowering ≤ 3 s, fallback ≤ 10 s (SC-007); broker overhead < 15 ms per call.
**Constraints**: nothing of a pack reaches the network, a session, Portalab's storage or the seal; protected
pages carry no pack content; every existing test and example pack keeps passing (SC-008); members' choices
unchanged.
**Scale/Scope**: 607 API operations to resolve (≈ 120 labelled exposable in v1); a handful of complete
interfaces; ≤ a few hundred members.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] I. Product Integrity — PASS: no rule changes; committing actions keep their server rules; confirmations
  add a step, never a different outcome.
- [x] II. Modular Architecture — PASS: labels declared by each module (`modules/<m>/exposure.py`) into a
  capability registry; seal owned by `identity`; interfaces by `visuals`; no cross-module import.
- [x] III. Extensibility First — PASS: complete interfaces are a new extension point with a stable,
  versioned protocol; Portalab's interface stays the default and fallback.
- [x] IV. Event-Driven Domain — PASS: `visuals.interface.misbehaved` and reports through the outbox; topics
  forwarded from the existing stream.
- [x] V. Source of Truth & Data Integrity — PASS: seal in PostgreSQL; acceptance recorded on the version;
  nothing duplicated client-side but per-viewer conveniences.
- [x] VI. Security & Authorization — PASS: default deny for operations, broker + server double check, top-layer
  trust UI, separate origin, sandbox CSP per kind, rate limits, audit.
- [x] VII. Privacy by Design — PASS: interfaces read only what the member may, through labelled reads; seal
  personal data exported/deleted with the account; images handed as bytes, no tokens.
- [x] VIII. Testability & Quality — PASS: SC-001…SC-010 mapped to suites (quickstart); isolation campaign
  extended.
- [x] IX. Resilience & Graceful Degradation — PASS: heartbeat, budgets, light version, Portalab fallback,
  safe mode.
- [x] X. UX Consistency — PASS: trust UI is one component everywhere; appearance and account pages use the page
  kit.
- [x] XI. Functional State vs Presentation — PASS: interfaces present; Portalab decides and states prices,
  rarities, draws.
- [x] XII. Accessibility — PASS: confirmations are modal dialogs with focus trap and announcements; interfaces
  failing the floor are flagged; members keep Portalab's interface.
- [x] XIII. Observability & Auditability — PASS: operations via interfaces audited with the interface;
  failures counted per element.
- [x] XIV. Deterministic Business Rules — PASS: draws stay server-side, shown by Portalab first.
- [x] XV. Internal Economy Integrity — PASS: purchases/openings only through confirmed, server-checked
  operations; interfaces as products follow 028's review.
- [x] XVI. AI Safety & Boundaries — N/A (AI routes forbidden to interfaces in v1).
- [x] XVII. Search and AI Independence — N/A.
- [x] XVIII. Configuration Hierarchy — PASS: pack origin port/URL are bootstrap settings with safe defaults;
  budgets and rate limits have defaults.
- [x] XIX. Versioning & Evolution — PASS: pack format 1 extended (new type only); broker protocol versioned in
  the context (`protocol: 1`); 028 packs unchanged.
- [x] XX. Simplicity & Maintainability — PASS: no dependency; the 028 bootstrap, registry, review and
  isolation tooling are reused.

Post-design re-check (after Phase 1): unchanged — all PASS; no Complexity Tracking entry.

## Project Structure

### Documentation (this feature)

```text
specs/029-trusted-interfaces/
├── plan.md
├── research.md          # R1–R20
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── broker-protocol.md
│   ├── exposure-catalog.md
│   ├── api-contracts.md
│   ├── pack-format-app.md
│   └── ui-contracts.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
backend/src/portalab/
├── capabilities/exposure.py                    # NEW labels, registry, resolution, forbidden prefixes
├── modules/<m>/exposure.py                     # NEW per-module label tables (media, community, dashboard,
│                                               #   marketplace, gamification, notifications, content, search…)
├── modules/identity/seal/                      # NEW seal model, service, routes (/me/seal), privacy contributor
├── modules/visuals/
│   ├── manifest.py, analysis.py                # interface_app type, app block, hardening rules (R10, R16)
│   ├── interfaces.py                           # NEW live interfaces, choice validation, accepted operations
│   ├── sandbox.py                              # bootstrap: app mode, call/subscribe/place, health, texts, exit
│   └── api/routes.py                           # /visuals/interfaces, draft operations, reports reasons
├── modules/ui/settings.py                      # ui.interfaceApp
├── app/pack_origin.py                          # NEW second-port ASGI app (static sandbox documents)
├── app/interfaces.py                           # NEW X-Portalab-Interface check, rate limit, audit
├── app/exposure_api.py                         # NEW GET /exposure
├── app/cli.py, core/settings.py                # serve on two ports; PACK_ORIGIN_PORT / PACK_ORIGIN_URL
└── migrations/identity/versions/…_seals.py

frontend/src/
├── trust/                                      # NEW <portalab-trust>, confirmTrusted, ExitControl, SafeMode,
│                                               #   seal drawing (48 symbols × 12 colours)
├── design-system/visuals/
│   ├── broker.ts                               # NEW call checks, confirm, fetch, scrub, subscribe
│   ├── interfaceHost.tsx                       # NEW full-screen app frame, context, fallback, host components
│   ├── budget.ts                               # NEW visual budgets (extends motion/budget.ts)
│   ├── cssGuard.ts                             # hardening rules + shield for look sheets (R10, R11)
│   └── registry.ts, sandbox.ts                 # pack origin documents; protected-page withdrawal (R9)
├── features/account/SealPicker.tsx             # NEW
├── features/appearance/InterfacePicker.tsx     # NEW
├── features/visuals/steps/{ReviewStep,TestStep}.tsx   # operations acceptance, app measures & probes
├── features/marketplace/…, features/media/…    # committing flows through confirmTrusted
└── shell/AppShell.tsx                          # interface host, safe mode banner, protected pages
sdk/interface/                                  # NEW types (generated), simulator.js, template/
examples/visual-packs/teletext/                 # NEW example complete interface
frontend/tests/{unit/trust, unit/visuals, e2e/trust, e2e/interfaces}/
backend/tests/{unit/test_exposure_catalog.py, unit/visuals/test_hardening.py,
               integration/identity/test_seal.py, integration/visuals/test_interfaces.py,
               security/test_interface_requests.py}
```

**Structure Decision**: existing web-application layout; one new capability (exposure), labels beside each
module, the seal inside `identity`, interfaces inside `visuals`, the trust layer as a frontend area of its
own (`frontend/src/trust/`) kept outside the design system so no theme or pack reaches it.

## Delivery slices (for /speckit.tasks)

1. **Foundation**: exposure capability + module labels + `GET /exposure` + route-wide test; seal (table,
   API, privacy); pack origin second port + sandbox documents per kind; settings.
2. **US1 Trust layer** (P1): `<portalab-trust>`, `confirmTrusted` on Portalab's committing flows, seal picker,
   exit control + shortcut, safe mode, protected pages without pack content.
3. **US2 Hardened looks** (P1): analysis rules, guard neutralisation, confinement CSS, shield for looks,
   `data-protected` on Portalab's words, built-in packs adapted, findings « to update ».
4. **US3 Complete interfaces** (P1): `interface_app` type and analysis, bootstrap app mode, broker, interface
   host (context, equivalents, fallback, heartbeat), member choice, Teletext example (first version).
5. **US4 Operations review & server check** (P2): Review acceptance, run-time refusal, server middleware,
   rate limits, audit.
6. **US5 Host components** (P2): place/move/unplace, player, reader, avatar, booster stage.
7. **US6 Budgets** (P2): health reports, quality, fallback, notices, counting.
8. **US7 Authoring** (P3): SDK generation, simulator, template, offline analysis, Test step measures &
   probes, docs.
9. **Polish**: isolation campaign extended, e2e journeys (seal on every committing action, read comparison),
   accessibility sweep, OpenAPI/client regeneration, full gates on the POC.

## Complexity Tracking

No constitution violations — section intentionally empty.
