# Implementation Plan: Confined Extensions

**Branch**: `030-confined-plugins` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/030-confined-plugins/spec.md`

## Summary

A plugin's code stops running inside Portalab. Each confined plugin runs in a **process of its own** that
confines itself with the kernel before loading any plugin code — Landlock (files and TCP), seccomp (no
socket, no exec, no fork, no ptrace, no signal), rlimits, an empty environment — and talks to Portalab only
through JSON lines on its pipes. Inside it, the plugin calls 023's **same SDK** (`register(ctx)`); the context
records its contributions and forwards every capability request to Portalab, which checks it against the
**grants** the Admin accepted at review: its own storage (run by Portalab as the plugin's login role), its
operations (permission checked, committing ones confirmed by Portalab's own dialog with the exact content),
portal data through **029's exposure catalog**, listed hosts only (SSRF-guarded, secrets injected by
Portalab), live channels, events, jobs, notifications, search, privacy and product types. Its pages and
**slot contributions** (navigation, home, media, player, settings…) are declarative blocks **drawn by
Portalab**; custom visuals are 028 sandboxed elements. Attempts outside the grants are recorded and quarantine
the plugin (023's guard). 023's plugins keep working: declarative unchanged, code plugins running as before
on upgraded installs (warning) until they declare `runtime = "confined"`. Five examples (Forum, Chat, a
product type, Moments, Home sections), an SDK simulator and template, and the deployment hardening of #144
(read-only image, outbound allow-list, per-module database roles behind a switch, audit copied off the
machine) complete it.

## Technical Context

**Language/Version**: Python 3.12 (backend, plugin processes), TypeScript 5.9 on Node 22 (frontend)
**Primary Dependencies**: existing FastAPI, Pydantic 2, SQLAlchemy 2 async + asyncpg, httpx, cryptography
(`SecretBox`), React 19, TanStack Query. **No new dependency**: Landlock and seccomp through `ctypes`
syscalls (x86_64 and aarch64 numbers), the pipes protocol on asyncio subprocesses.
**Storage**: PostgreSQL — `plugins.grants`, `plugins.attempts`, `plugins.network_calls`,
`plugins.secret_settings`, `plugins.slot_settings`, `plugins.confirmations`; columns `runtime`,
`confinement` on `plugins.plugins`; 023's `plugin_<key>` schemas and roles (role gains LOGIN); user
settings `ui.hiddenContributions`, `ui.coreOrder`.
**Testing**: pytest (unit: seccomp/Landlock builders, protocol framing, manifest v2, SSRF guard, statement
filter; integration: host lifecycle, grants, storage as role, portal calls, network, live, product type,
privacy, migration; security: the isolation campaign of the probe plugin, secrets; migrations: upgrade
paths), Vitest (blocks, slots, confirmation, admin review), Playwright (Forum, Moments, Home sections,
admin review, a11y).
**Target Platform**: the single Linux image (`serve` / `worker`) as user 10001 under Docker's default
seccomp profile; Linux ≥ 6.7 for Landlock TCP rules (else held / weak mode).
**Project Type**: web application (backend modules + SPA).
**Performance Goals**: plugin call overhead ≤ 50 ms p95 (SC-005; target ≤ 5 ms for the pipe round trip);
chat delivery ≤ 1 s p95 with 50 members (SC-004); slots ≤ 100 ms added p95 (SC-010); child start ≤ 1.5 s.
**Constraints**: nothing of the portal reachable from the child but through Portalab; 023's tests pass
unchanged (SC-006); no secret ever sent to a child (SC-008); memory 384 MiB per child by default.
**Scale/Scope**: a handful of plugins per portal (≤ 20 children per process), ≤ a few hundred members.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] I. Product Integrity — PASS: plugins ask, Portalab decides; economy, permissions and privacy rules stay
  their owners'; the Skip-intro example duplicating a built-in feature was surfaced and replaced (spec Q4).
- [x] II. Modular Architecture — PASS: everything new is in `modules/plugins` and `plugins_runtime`; portal
  data only through the capability-backed exposure catalog; per-module roles enforce the boundary (R14c).
- [x] III. Extensibility First — PASS: 023's extension points and SDK are reused as they are; slots are new
  extension points; disabling keeps data; core works without plugins.
- [x] IV. Event-Driven Domain — PASS: plugin events through 007's backbone, validated and idempotent (023).
- [x] V. Source of Truth & Data Integrity — PASS: plugin data in its own schema; migration to confinement
  keeps it; quotas refuse writes, never delete.
- [x] VI. Security & Authorization — PASS: default deny for capabilities, operations, hosts and slots; the
  server checks every call; committing actions confirmed by Portalab; secrets kept by Portalab.
- [x] VII. Privacy by Design — PASS: plugins with personal data must export and erase (FR-015); live
  delivery honours blocks; members see what a plugin reads.
- [x] VIII. Testability & Quality — PASS: every SC has a suite (quickstart.md); the isolation campaign is
  automated.
- [x] IX. Resilience & Graceful Degradation — PASS: a child's failure fails its calls only; restart with
  backoff; quarantine; the portal runs without the confined runtime (plugins held).
- [x] X. UX Consistency — PASS: plugin pages and slots are drawn by the design system.
- [x] XI. Functional State vs Presentation — PASS: interfaces style slots through tokens only.
- [x] XII. Accessibility — PASS: blocks are Portalab components (keyboard, screen readers, reduced motion).
- [x] XIII. Observability & Auditability — PASS: grants, revocations, secret changes audited; attempts and
  network calls recorded; audit copied off the machine (FR-026).
- [x] XIV. Deterministic Business Rules — PASS: deterministic slot ordering (023's resolution + Admin order).
- [x] XV. Internal Economy Integrity — PASS: plugins never touch coins (product hooks only, shop's rules).
- [x] XVI. AI Safety & Boundaries — N/A (023's `ai_tool` contributions proxied unchanged).
- [x] XVII. Search and AI Independence — PASS: a plugin's search provider timing out never delays core
  results (008's budget).
- [x] XVIII. Configuration Hierarchy — PASS: Global → Plugin settings → User hidden contributions.
- [x] XIX. Versioning & Evolution — PASS: manifest v1 valid; in-process plugins keep running on upgrade.
- [x] XX. Simplicity & Maintainability — PASS with one entry in Complexity Tracking (per-module roles).

## Project Structure

### Documentation (this feature)

```text
specs/030-confined-plugins/
├── plan.md · research.md (R1–R17) · data-model.md · quickstart.md
├── contracts/ child-protocol.md · manifest-v2.md · http-api.md
└── tasks.md
```

### Source Code

```text
backend/src/portalab/
├── plugins_runtime/
│   ├── __init__.py                 # 023's in-process loader (unchanged)
│   └── confined/
│       ├── kernel.py               # Landlock + seccomp + rlimits through ctypes; probe()
│       ├── protocol.py             # framing, message types, limits
│       ├── child.py                # child entry: confine, hello, register(ctx), serve calls
│       ├── recording.py            # the child's PluginContext (023 surface + db/portal/http/live/settings)
│       └── host.py                 # ConfinedHost: spawn, supervise, call, ask-dispatch, attempts
├── modules/plugins/
│   ├── manifest/schema.py          # v2 (capabilities, routes labels, slots, secret settings)
│   ├── grants/                     # service + admin API (grants, revoke, secrets, runtime)
│   ├── capabilities/               # the parent side of each ask: storage.py, portal.py, network.py,
│   │                               #   live.py, notify.py, events.py, jobs.py
│   ├── confirmations.py            # committing routes (R6)
│   ├── slots/                      # registry, member/admin visibility, API
│   ├── lifecycle/service.py        # runtime choice, held states, migration path
│   └── api/runtime.py              # dispatcher → proxies; slots endpoints
├── app/egress.py                   # outbound allow-list hook (R14b)
├── core/db.py                      # module roles switch (R14c)
├── modules/administration/audit_offsite.py   # syslog / file sink (R14d)
└── sdk/__init__.py · sdk/pages.py · sdk/slots.py   # SDK 2.0 (additive)

backend/tests/{unit,integration,security,migrations}/plugins/ · tests/fixtures/plugins/probe/
examples/plugins/{forum,chat,commission,moments,home-sections}/

frontend/src/features/plugins/      # blocks (new kinds), PluginConfirm, slots host <Slot name=…>
frontend/src/features/admin/plugins/ # review of capabilities, attempts, secrets, runtime, slot order
frontend/src/features/media/player/  # player.overlay / player.button slots
frontend/src/features/home/, shell/  # home.section, nav slots
frontend/tests/{unit,e2e}/plugins/
deploy/compose.example.yml           # read_only + tmpfs
```

**Structure Decision**: the web application layout of the repository; confinement in `plugins_runtime`
(below modules, imported by `modules/plugins` only), parent-side capabilities in `modules/plugins`.

## Delivery slices

1. **Slice A — Confinement and the Forum (P1: US1, US2, US6)**: kernel confinement, protocol, host,
   manifest v2, grants and review, storage as role, operations with labels and confirmations, portal data,
   network and secrets, events/jobs/notifications/search/privacy proxied, attempts and quarantine, 023
   compatibility and migration, the probe campaign, the Forum example, admin review UI.
2. **Slice B — Extensions as one package (US1b)**: slots registry and API, Portalab-drawn slot hosts
   (nav, home, media, player, settings, profile), member and Admin visibility, Moments and Home sections.
3. **Slice C — Live and the shop (US3, US4)**: live channels and presence, Chat; product type hooks,
   Commission, fault injection.
4. **Slice D — Hardening and authoring (FR-023–027, US5 completion, US7)**: egress allow-list, read-only
   image check, audit off-site, module roles behind the switch, SDK simulator, template, validate report.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Per-module database roles (`SET LOCAL ROLE` per unit of work) | FR-025, #144: a flaw in one module must not read another's data | One role for the app gives every module every table; delivered last behind `security.moduleRoles` (off by default) so nothing breaks before the suite passes with it on |
| Hand-built seccomp BPF and Landlock via `ctypes` | Unprivileged kernel confinement with no new dependency | `python-landlock`/`pyseccomp` add native dependencies to the image; namespaces need privileges Docker refuses |
