---
description: "Task list — Marketplace (spec 015)"
---

# Tasks: Marketplace

**Input**: `specs/015-marketplace/` · **Branch**: `015-marketplace` · **Roadmap**: **Slice A** (Phases 1–6) = step 25 *Community Projects / Funding*; **Slice B** (Phases 7–13) = step 26 *Marketplace* · **Tests**: included.
Abbrev: **`MK/`** = `backend/src/portalab/modules/marketplace`, **`CAP/`** = `backend/src/portalab/capabilities/marketplace`, **`FM/`** = `frontend/src/features/marketplace`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/outbox/UoW · `D-002` deletion saga · `D-003` authz/`ConfirmationService`/`AuditSink` · `D-007` events · `D-010` `send`/categories · `D-013` economy (**follow-ups: `reserve/release/consume`, `spend(uow)`**) · `D-012` proposals/votes (`ProjectLifecycle` consumer) · `D-014` `CampaignReader` · `D-020` settings · `D-021` retention · `D-022` UI · `D-026` localization · `D-008` search SDK · `D-009/017/022/024` entitlement consumers · `D-023` `ExtensionActivation` (step 27; stubbed).

## Phase 1: Setup (Slice A)
- [X] T001 Create `CAP/__init__.py`, `MK/{projects,funding,resolution,products,types,eligibility,purchase,activation,refunds,grants,revocation,quota,entitlements,providers,api,models}/__init__.py`, `backend/migrations/marketplace/versions/`, `FM/{catalog,product,owned,projects,admin}/`, `backend/tests/{unit,integration,contract,security}/marketplace/`, `frontend/tests/{unit,e2e}/marketplace/`
- [X] T002 [P] Declare settings (`marketplace.refundDefaults.<type>`, `.access.allowedPermissions`, `.funding.minAmount|maxPerUser|defaultRules`, `.quota.kinds`, `.activationRetryMinutes`) in `MK/settings.py`; permissions `marketplace.read|purchase` (default grants for active accounts), `marketplace.manage|grant|revoke|refund|audit`, `projects.manage` (Admin; sensitive, audited) in `MK/permissions.py`; notification categories `marketplace.purchase|refund|revocation|project` (010); event types with 007
- [X] T003 [P] Register retention targets and the 020/021 export+erasure participant `MK/privacy.py` implementing the R6 deletion policy (all reservations released then destroyed with the account's Coins whatever the project state; funding rows anonymized; ownerships tombstoned)

## Phase 2: Foundational — schema, ports (Slice A)
### Tests first
- [X] T004 [P] Write `backend/tests/integration/marketplace/test_schema_projects.py`: tables/constraints, append-only `project_state_history`, `funding_rules` immutable after `rules_frozen_at`, FKs only intra-module/`identity.users(id)`
- [X] T005 [P] Write `backend/tests/contract/marketplace/test_economy_port.py`: `EconomyService.reserve/release/consume` conformance kit (fake until 013 follow-up): reserve decreases available balance without consuming, insufficient funds refused, release = new transaction, consume final, idempotency, balance never negative
### Implementation
- [X] T006 Implement `CAP/` contracts (`ProjectLifecycle`, `EntitlementReader`, `ProductType`, `ActivationHandler`; consumed 024 `RequestQuotaService` stub) and `MK/models` + Alembic revision (slice A tables: projects, project_state_history, project_fundings, project_notes)

## Phase 3: US7 — Lifecycle state machine and Community integration (P1) 🎯 MVP (Slice A)
**Independent test**: a project moves idea → release with audited, permissioned transitions; Community can register and read it.
- [X] T007 [P] [US7] Write `backend/tests/unit/marketplace/test_project_state_machine.py`: allowed transitions (`idea→proposal→open→validation→development→beta→released`, off-ramps `rejected|abandoned`), forbidden transitions, `accepts_votes` true only for `idea|proposal|open`, funding only in `open`, rules frozen at `open`, optimistic `version`
- [X] T008 [P] [US7] Write `backend/tests/integration/marketplace/test_project_lifecycle_api.py`: Community `register` creates a project once per proposal; promote/open/validate/transition/abandon require `projects.manage`, confirmation and audit; every change appends history and emits `project.status_changed` (dedup `(project, seq)`); validation is a gate informed by (not bound to) votes/funding
- [X] T009 [US7] Implement `MK/projects/service.py` (state machine, history, events), the `ProjectLifecycle` capability implementation for 012, and admin routers `POST /admin/projects/{id}/promote|open|validate|transition|abandon|reject`, `GET /projects`, `GET /projects/{id}`

## Phase 4: US7 — Funding with reservation (P1)
- [X] T010 [P] [US7] Write `backend/tests/integration/marketplace/test_funding.py`: funding only in `open`; acknowledgement of non-guarantee mandatory (`project.acknowledgement_required`); amount limits; reservation transaction via `EconomyService.reserve` (atomic with `project_fundings`); insufficient Coins refused, balance never negative; concurrent fundings consistent; funding independent of voting (no vote required, no vote created); `project.funding_added` emitted once per idempotency key
- [X] T011 [US7] Implement `MK/funding/service.py`, router `POST /projects/{id}/fund`, `GET /me/fundings`, and the non-guarantee notice text catalog keys (026)

## Phase 5: US7 — Resolution: refund and consume (P1)
- [X] T012 [P] [US7] Write `backend/tests/integration/marketplace/test_resolution.py`: reject/abandon ⇒ all reservations released per frozen rules (new refund transactions, `funding_released` events); release ⇒ consumed per rules (all at release or per milestone percentages); never silent or partial without rule; idempotent job re-runs; ledger/reservation reconciliation equals zero drift; deletion of a funder destroys all of their reservations in every project state (R6) and project totals are recomputed
- [X] T013 [US7] Implement `MK/resolution/service.py` (release/consume/milestones, deletion handling, reconciliation job) and notifications `marketplace.project` (status changes, refunds) via 010 with coalescing
- [X] T014 [US7] Implement frontend `FM/projects/{ProjectPage,Timeline,FundingPanel,MyFundings}.tsx` (state timeline with icon+text, published rules, non-guarantee notice, accessible) and admin `FM/admin/ProjectConsole.tsx`; wire Community slice D stubs to the real `ProjectLifecycle`

## Phase 6: Slice A closure
- [X] T015 [P] Write `backend/tests/security/marketplace/test_projects_authz.py`: only Admin transitions/validates; funders see own funding, aggregates public, other funders' identities private; IDOR on fundings; audit completeness; no secrets in events
- [X] T016 [P] Register `marketplace` with Observability (stuck states, reserved vs consumed vs released totals, reconciliation drift) in `MK/observability.py`; add `/projects*`, `/me/fundings`, `/admin/projects*` routes to the permission-matrix test and OpenAPI client
- [X] T017 Run `specs/015-marketplace/quickstart.md` steps 1–2 end-to-end; record deviations, open product confirmations (funding formulas, deletion handling) and the 013 follow-up status

## Phase 7: Catalog and product model — US1, US8 (Slice B, step 26)
- [ ] T018 [P] [US1] Write `backend/tests/integration/marketplace/test_catalog.py`: categories, product types, detail shows type/price/conditions/refund policy and the viewer's ownership/eligibility; availability states `draft|available|unavailable|archived`; archived hidden from new purchase but visible to owners; multilingual names via 026; search provider `product` (008 conformance)
- [ ] T019 [P] [US8] Write `backend/tests/integration/marketplace/test_product_admin.py`: publish/price/condition/refund-policy changes create new versions (history never reinterpreted), are sensitive, confirmed and audited; type registry extension without schema change
- [ ] T020 [US1] Implement Alembic revision for slice B tables (categories, products, product_versions, ownerships, refunds), `MK/products/service.py`, `MK/types/registry.py` (`register_product_type` baseline types), routers `GET /marketplace/categories|products[/{key}]`, search provider (008)
- [ ] T021 [US8] Implement admin routers `/admin/marketplace/products*` with versioning/audit and frontend `FM/catalog/{CatalogPage,ProductCard}.tsx`, `FM/product/ProductDetail.tsx`, `FM/admin/ProductEditor.tsx`

## Phase 8: US2 + US3 — Acquisition with conditions; ownership (P1)
- [ ] T022 [P] [US2] Write `backend/tests/unit/marketplace/test_eligibility.py`: free/Coins/min level/achievement/campaign/role conditions; strict AND (all must hold); unmet conditions returned **by name**; evaluated server-side; ports unavailable ⇒ fail closed with explicit reason
- [ ] T023 [P] [US3] Write `backend/tests/integration/marketplace/test_acquisition.py`: atomic acquisition (fault injection after spend ⇒ no orphan spend/ownership); `Idempotency-Key` replay returns the same ownership; concurrent double acquire ⇒ one; already-owned permanent product refused; `repeatable` allowed; price paid/conditions/version snapshot stored; Coins charged only via ledger; archived product still accessible to owners
- [ ] T024 [US2] Implement `MK/eligibility/service.py` and `MK/purchase/service.py` (UoW with `EconomyService.spend(uow)` or idempotent saga + compensating refund), router `POST /marketplace/products/{key}/acquire`, events `marketplace.purchase|unlock`, and frontend purchase flow `FM/product/{ConditionsChecklist,PurchaseDialog}.tsx`

## Phase 9: US4 — Immediate plugin activation unless configuration required (P1)
- [ ] T025 [P] [US4] Write `backend/tests/integration/marketplace/test_activation.py`: widget/theme/statistic/badge/title/effect/feature/plugin/access handlers (fakes for 009/022/017/023/003); immediate activation on acquisition; `needs_configuration` until configured; incompatible/failed activation isolated (ownership kept, retry job, other features unaffected); `access` grants limited to the Admin allow-list and never Admin-reserved permissions, removed on revoke
- [ ] T026 [US4] Implement `MK/activation/{service,handlers}.py` (handlers per type, retry job), `POST /me/marketplace/owned/{id}/configure`, `EntitlementReader` implementation (`MK/entitlements/reader.py`) and frontend `FM/owned/{OwnedPage,NeedsConfiguration}.tsx`

## Phase 10: US5 — Purchase history, refunds (P1)
- [ ] T027 [P] [US5] Write `backend/tests/integration/marketplace/test_history_refunds.py`: history lists conditions/price/status; refund within policy = new ledger transaction referencing the original (never edits), ownership refunded; non-refundable labelled before purchase and refused with `marketplace.not_refundable`; partial percent policy; quota units consumed ⇒ non-refundable; `marketplace.refund` emitted once
- [ ] T028 [US5] Implement `MK/refunds/service.py`, routers `GET /me/marketplace/purchases|owned`, `POST /me/marketplace/owned/{id}/refund`, admin `POST …/refund`, and frontend `FM/owned/History.tsx`

## Phase 11: US5 — Grants, revocation, audit (P1)
- [ ] T029 [P] [US5] Write `backend/tests/security/marketplace/test_grants_revocation_audit.py`: grants marked `origin=grant` (optional expiry) and audited; revocation requires an enumerated ground + reason, removes access without rewriting history, notifies the user per preferences, refunds Coins-paid products unless ground `abuse`; every sensitive action (publish, price/condition change, refund, grant, revoke, archive) has an audit entry (actor/action/timestamp/context/result); only authorized roles
- [ ] T030 [US5] Implement `MK/grants/service.py`, `MK/revocation/service.py`, routers `POST /admin/marketplace/grants`, `POST /admin/marketplace/ownerships/{id}/revoke`, `GET /admin/marketplace/audit`, expiry job, notifications `marketplace.revocation`, and frontend `FM/admin/{Grants,Revocations,Audit}.tsx`

## Phase 12: US6 — Quota products with no paid priority (P1)
- [ ] T031 [P] [US6] Write `backend/tests/integration/marketplace/test_quota.py`: quota purchase spends Coins via the ledger and credits units through 024 `RequestQuotaService.add_units` (stub until 024); refund of unused units calls `remove_units`; Marketplace never consumes quota; **no input from ownership/quota to request ordering** (contract test against 024's queue ordering function: identical order for buyers/non-buyers); product definitions cannot declare a priority attribute (schema rejects)
- [ ] T032 [US6] Implement the quota activation handler `MK/activation/handlers/quota.py` (credit/debit units via 024 `RequestQuotaService`), and add the schema guard rejecting priority-like fields in product definitions

## Phase 13: Polish & cross-cutting
- [ ] T033 [P] Implement integrations: dashboard widget `marketplace.featured` (REQ-018, 009); `EntitlementReader` consumers contract tests for 009 (widget catalog), 022 (theme availability), 017 (`product_owned`), Community cosmetics sections; statistics pack `backend/definitions/packs/marketplace.json` (017); notification templates for purchase/refund/revocation (010); AI read tool `marketplace.catalog` (018)
- [ ] T034 [P] Write `backend/tests/security/marketplace/test_no_real_money.py`: no payment/real-money code paths or fields exist; Coins purchasable only via earning; idempotency on all money-like endpoints; amount/price validation (integers, bounds)
- [ ] T035 [P] Register slice B observability (activation failures/retries, purchases/refunds/grants, drift between ownership and ledger) in `MK/observability.py`; add `/marketplace*`, `/me/marketplace*`, `/admin/marketplace*` to the permission-matrix test and OpenAPI client; write `docs/marketplace.md` (types, conditions, refund/revocation policy, funding rules, port contracts, follow-ups for 013/009/022/017/024/023)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T036 [P] Expose owner-tagged registration on the product-type registry: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/marketplace/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T037 Run `specs/015-marketplace/quickstart.md` steps 3–7 end-to-end; record deviations and open product confirmations (OQ-70..74 defaults, per-user vs portal-level activation)

## Dependencies & Order
**Slice A**: Setup → Foundational → US7 lifecycle → funding → resolution → closure (needs 013 follow-up or compliant fake). **Slice B**: catalog → acquisition → activation → refunds → grants/revocation → quota → polish. US2 needs eligibility ports (013/014/003); US4 handlers need consumers (009/022/017) or fakes; US6 needs 024's `RequestQuotaService` (stub until 024).
**Parallel examples**: T004/T005 · T007/T008 · T018/T019 · T022/T023 · T029 with T031 · T033/T034/T035.
**MVP (Slice A)**: Phases 1–4 (lifecycle state machine and reserved funding); **MVP (Slice B)**: Phases 7–8 (catalog and atomic acquisition).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
