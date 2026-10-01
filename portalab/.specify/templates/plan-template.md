# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Confirm the plan complies with each applicable principle of `/.specify/memory/constitution.md`
(v1.0.0). Mark each PASS / N/A, or record the deviation in Complexity Tracking.

- [ ] I. Product Integrity — no business rule weakened; contradictions surfaced, not silently resolved.
- [ ] II. Modular Architecture — Modules depend on Capabilities; new Service is additive, no Module rewrite.
- [ ] III. Extensibility First — reuses extension points; Core/Modules work without optional Plugins; plugin disable keeps data.
- [ ] IV. Event-Driven Domain — reaction via events (not direct service coupling); idempotent consumers; occurred_at vs received_at; provenance retained.
- [ ] V. Source of Truth & Data Integrity — defined source of truth; no silent history destruction on sync/outage; migrations preserve history.
- [ ] VI. Security & Authorization — server-side default-deny; no UI-only enforcement; sensitive actions confirmed + audited; secrets not leaked to client.
- [ ] VII. Privacy by Design — historized ≠ public; visibility prefs honored; admin override preserves/restores preference.
- [ ] VIII. Testability & Quality — acceptance criteria are test-verifiable (nominal/errors/permissions/privacy/edge/sync/events/degraded/extensibility).
- [ ] IX. Resilience & Graceful Degradation — partial failure stays partial; functional states distinguishable; staleness identifiable.
- [ ] X. UX Consistency — uses the shared Design System; no dead-ends; page answers where/what/what's-happening/next.
- [ ] XI. Functional State vs Presentation — logic independent of theme; themes/personalization don't change rules; accessibility prefs win.
- [ ] XII. Accessibility — keyboard/touch/responsive/reduced-motion/no-sound/contrast; mobile functionally complete.
- [ ] XIII. Observability & Auditability — sensitive actions audited (actor/action/time/context/result); self-diagnosis; actionable errors.
- [ ] XIV. Deterministic Business Rules — deterministic/traceable outcomes; no history rewrite; rule versioning where history is affected.
- [ ] XV. Internal Economy Integrity — Coins virtual-only; traceable transactions; non-negative; refunds as new transactions; destroyed on deletion.
- [ ] XVI. AI Safety & Boundaries — AI within user permissions; sensitive AI actions obey same rules; AI failure doesn't break classic functions.
- [ ] XVII. Search and AI Independence — classic search never waits on AI; neither outage disables the other.
- [ ] XVIII. Configuration Hierarchy — Global → Module → Plugin → User; policies constrain; prefs retained when permitted; usable defaults.
- [ ] XIX. Versioning & Evolution — historical data/transactions not reinterpreted; existing workflows preserved or deviation justified.
- [ ] XX. Simplicity & Maintainability — no tech/abstraction without a product need; no duplicated cross-cutting mechanisms.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
