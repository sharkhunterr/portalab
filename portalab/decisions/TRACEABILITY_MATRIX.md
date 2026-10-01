# Final Requirements Traceability Matrix — Personal Extensible Portal

**Created**: 2026-10-01
**Sources of truth**: `product/PRODUCT_BLUEPRINT.md`, `.specify/memory/constitution.md` (v1.0.0),
`decisions/CANONICAL_DECISIONS.md`, and all 26 specifications (`specs/001` … `specs/026`).
**Purpose**: Prove the Product Blueprint is fully represented by the specifications. **Traceability, not
scoring.** No product decision is modified; no requirement invented.

## Methodology (Blueprint → atomic requirements)

The Blueprint contains 26 headed blocks. Per the instruction *"do not collapse distinct requirements…
split where necessary"*, blocks containing multiple independent requirements are atomized. This yields
**58 atomic requirements (REQ-001…REQ-058)**. (The brief's "56" count differs by 2: the **Core Principles**
block is atomized into 9 and the **Coins** block into 4; collapsing Product Loop + Final Definition into
identity statements would give 56. The matrix uses the faithful 58-entry atomization and flags the
derivation here rather than forcing a number.)

**Column legend** (per the required columns): ID · Blueprint Block · Summary · Type · Primary Spec ·
Supporting Specs · FR/US/AC (Functional Requirement IDs; User Story IDs; acceptance criteria = the
numbered acceptance scenarios under those US) · Canonical Owner · Dependencies · Coverage · Status
(all = **Specified (Draft)** — every spec is Status: Draft). Notes appear as footnotes `[n]`.

Coverage states: **FULL / PARTIAL / MISSING / CONFLICTING / NOT_APPLICABLE**.

## 1. Requirements Traceability Matrix

| ID | Blueprint Block | Summary | Type | Primary | Supporting | FR / US / AC | Owner | Dependencies | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| REQ-001 | Vision | Primary entry point / experience layer above connected services | Core Product | 004 | 001, 009, 008 | 004 FR-001..004; US1 | Portal Core (004) | 005, 007 | FULL |
| REQ-002 | Vision | Scope boundary: NOT dashboard/Plex-frontend/monitoring/social/CMS/standalone-marketplace | Core Product | 001 | 024, 006, 012, 015 | 001 US1; 024 (non-goal); 012 FR-003 | Portal Core (004) | — | FULL `[1]` |
| REQ-003 | Architecture | Hierarchy Portal→Core/Modules/Plugins/Connectors/Services/Capabilities | Extensibility | 023 | 001, 005 | 023 FR-001..004; US1 | Plugins/Extensibility (023) | 005 | FULL |
| REQ-004 | Architecture | Cross-cutting systems set (AI, Search, Events, History, Sync, Automation, Gamification, Statistics, Notifications, Privacy, Observability) | Core Product | 001 | 007,008,018,019,013,017,010,021,025 | spec-level (each owner) | Portal Core (004) | all | FULL `[1]` |
| REQ-005 | Core Principle | Modules depend on capabilities, not concrete services | Integration | 005 | 024, 006, 023 | 005 FR-001..004; US1-2 | Connectors (005) | — | FULL |
| REQ-006 | Core Principle | Events decouple features | Data | 007 | all consumers | 007 FR-005..009; US1/US4 | Events & History (007) | — | FULL |
| REQ-007 | Core Principle | Historized ≠ public | Privacy | 021 | 007, all | 021 FR-010 (invariant); 007 FR-016 | Permissions/Privacy (021) | 007 | FULL |
| REQ-008 | Core Principle | AI never more rights than the current user | Security / AI | 018 | 003, 008 | 018 FR-001..004; US1; SC-001/002 | AI (018) | 003 | FULL |
| REQ-009 | Core Principle | Permissions server-side (default-deny) | Security | 003 | all | 003 FR-001..005; US1 | Permissions/Privacy (003) | — | FULL |
| REQ-010 | Core Principle | Themes change presentation, not functional truth | UX | 022 | 004, 009 | 022 FR-001..004; US1/US8 | Accessibility/Themes (022) | — | FULL |
| REQ-011 | Core Principle | External services remain source of truth for native data | Data | 005 | 024, 021 | 005 FR-019..021; US6 | Connectors (005) | — | FULL |
| REQ-012 | Core Principle | Partial failures must not break unrelated functions | Performance | 004 | 006, 009, 025 | 004 FR-025..028; US7 | Portal Core (004) | — | FULL |
| REQ-013 | Core Principle | System evolves without rewriting the core | Extensibility | 023 | 005, 015 | 023 FR-021/028; US6 | Plugins/Extensibility (023) | — | FULL |
| REQ-014 | Modules | Module set: Home, Media, Community, Statistics, Support, Marketplace, Services, News, Calendar, Administration | Core Product | 004 | 009,024,012,017,016,015,006,011,020 | per-module specs | Portal Core (004) | — | FULL `[2]` |
| REQ-015 | Plugins | Plugin can add pages/features/widgets/statistics/permissions/config/events & enrich detail pages | Extensibility | 023 | 009, 017, 003, 007 | 023 FR-011..018; US4-5 | Plugins/Extensibility (023) | 003, 007, 009 | FULL |
| REQ-016 | Plugins | Marketplace plugins activate immediately after purchase unless admin config required | Marketplace | 015 | 023 | 015 FR-012; US4 | Marketplace (015) | 023 | FULL |
| REQ-017 | Connectors/Services/Capabilities | Connector = external integration; Service = instance; Capability = exposed ability | Integration | 005 | 006, 024 | 005 FR-001..004/010; US1 | Connectors (005) | — | FULL |
| REQ-018 | Home | Home widgets incl. current activity, events, news, requested media, progression, service status, community projects, Since-Last-Login, Marketplace | UX | 009 | 024,006,011,013,012,015 | 009 FR-016; US5 + widget catalog | Dashboard (009) | 007,024,013 | FULL |
| REQ-019 | Home | Widgets load independently | UX / Performance | 009 | 004 | 009 FR-001..003; US1; SC-001 | Dashboard (009) | — | FULL |
| REQ-020 | Community | Community features: Members, Activity, Leaderboards, Quests, Achievements, Community Projects, Proposals, Funding, Profile | Community | 012 | 013, 015 | 012 FR-001..025; US1-8 | Community (012) | 013, 015 | FULL |

| ID | Blueprint Block | Summary | Type | Primary | Supporting | FR / US / AC | Owner | Dependencies | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| REQ-021 | Community | No core friends/followers/DM/chat system (chat may be a future plugin) | Community | 012 | 023 | 012 FR-003/004; US (non-goals); SC-001 | Community (012) | — | FULL |
| REQ-022 | Gamification | Exactly three tracked values: XP, Contribution, Coins | Gamification | 013 | 012 | 013 FR-001; US1; SC-001 | Gamification (013) | — | FULL |
| REQ-023 | Gamification | Levels are derived progression tiers, not a fourth currency | Gamification | 013 | — | 013 FR-002/003; US2; SC-002 | Gamification (013) | — | FULL |
| REQ-024 | Coins | Coins strictly virtual/internal; no real-money purchase | Business Rule | 013 | 015 | 013 FR-022; SC-006 | Gamification (013) | — | FULL |
| REQ-025 | Coins | Coin balance normally never negative | Business Rule | 013 | 015 | 013 FR-021; US6; SC-005 | Gamification (013) | — | FULL |
| REQ-026 | Coins | Coins fully auditable / traceable transactions | Business Rule | 013 | 007, 003 | 013 FR-019/020; US6; SC-004 | Gamification (013) | 007 | FULL |
| REQ-027 | Coins | Remaining Coins destroyed on final account deletion | Business Rule / Privacy | 013 | 021, 002 | 013 FR-028/029; US8; SC-007 | Gamification (013) | 021, 002 | FULL |
| REQ-028 | Events (Campaigns) | Campaign defines dates/recurrence/multipliers/achievements/quests/notifications/themes/email | Gamification | 014 | 013, 010, 022 | 014 FR-001..013; US1-5 | Campaigns (014) | 013, 010 | FULL |
| REQ-029 | Events (Campaigns) | Multiple campaigns may overlap; conflict resolution is deterministic | Business Rule | 014 | 013 | 014 FR-014..017; US6; SC-003 (CD-024) | Campaigns (014) | 013 | FULL `[3]` |
| REQ-030 | Automations | WHEN→IF→THEN reactions; not a full n8n clone | Automation | 019 | 007, 010 | 019 FR-001..027; US1; SC-010 | Automations (019) | 007 | FULL |
| REQ-031 | Marketplace | Product types: plugins/widgets/statistics/themes/effects/badges/titles/quotas/features/community projects | Marketplace | 015 | 023, 022, 017 | 015 FR-001; US1 | Marketplace (015) | 023 | FULL |
| REQ-032 | Marketplace | Request quotas purchasable; paid processing priority does NOT exist | Marketplace / Business Rule | 015 | 024 | 015 FR-019/020; US6; SC-007 | Marketplace (015) | 013 | FULL |
| REQ-033 | Community projects | Every active account can vote; voting is free; no minimum level | Community / Business Rule | 012 | 002 | 012 FR-013/014; US5; SC-002 | Community (012) | 002 | FULL |
| REQ-034 | Community projects | Voting is independent from coin funding | Business Rule | 012 | 015 | 012 FR-016; US5; SC-003 | Community (012) | 015 | FULL |
| REQ-035 | Community projects | Funding does not guarantee implementation | Business Rule | 015 | 012 | 015 FR-026; US7; SC-009 | Marketplace (015) | 012 | FULL |
| REQ-036 | Community projects | Reserved funds refunded/consumed per published project rules | Business Rule | 015 | 013, 012 | 015 FR-023..025; US7 | Marketplace (015) | 013 | PARTIAL `[4]` |
| REQ-037 | Support | Tickets, incidents, Wiki, feedback, contextual help; Ticket=individual, Incident=systemic | Support | 016 | 011, 006 | 016 FR-001..013; US1-4; SC-001 | Support (016) | 011, 006 | FULL |
| REQ-038 | Support | AI may diagnose & prefill a ticket; user reviews before submission | Support / AI | 016 | 018 | 016 FR-017..021; US6; SC-004 | Support (016) | 018 | FULL `[5]` |
| REQ-039 | AI | AI can understand, search, explain, recommend, navigate, act | AI | 018 | 008, 024 | 018 FR-008..015; US2-5 | AI (018) | 008 | FULL |
| REQ-040 | AI | AI uses current user permissions; sensitive actions confirmed where appropriate | Security / AI | 018 | 003 | 018 FR-001..003/013; US1/US5; SC-003 | AI (018) | 003 | FULL |

| ID | Blueprint Block | Summary | Type | Primary | Supporting | FR / US / AC | Owner | Dependencies | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| REQ-041 | Search | Classic search results appear immediately; AI analyzes in parallel | Search | 008 | 018 | 008 FR-001; US1; SC-001 | Search (008) | 018 | FULL |
| REQ-042 | Search | Failure of one (search or AI) does not block the other | Search | 008 | 018 | 008 FR-002/003; US2; SC-002 | Search (008) | 018 | FULL |
| REQ-043 | Notifications | Notification, Alert, News, Email are distinct concepts | Notifications | 010 | 011 | 010 FR-001..004; US2; SC-001 | Notifications (010) | — | FULL |
| REQ-044 | Notifications | Channels: portal, email, sound, future push | Notifications | 010 | — | 010 FR-026/027; US8 | Notifications (010) | — | FULL `[6]` |
| REQ-045 | Notifications | User controls notification categories where policy allows | Notifications | 010 | 020, 021 | 010 FR-008..011; US3 | Notifications (010) | 020 | FULL |
| REQ-046 | Privacy | Visibility levels: Public, Community, Leaderboards-only, Private | Privacy | 021 | 012, 017 | 021 FR-001..004; US1 | Permissions/Privacy (021) | — | FULL |
| REQ-047 | Privacy | User preference and admin policy are separate | Privacy | 021 | 020 | 021 FR-005/006; US2 | Permissions/Privacy (021) | 020 | FULL |
| REQ-048 | Privacy | Admin visibility override preserves user preference; removal auto-restores it | Privacy | 021 | 003, 020 | 021 FR-005..008; US2; SC-003 | Permissions/Privacy (021) | 020 | FULL |
| REQ-049 | Dashboard | Users add/remove/reorder/resize/configure widgets within policy | UX | 009 | 022 | 009 FR-004..008; US2; SC-002 | Dashboard (009) | 020 | FULL |
| REQ-050 | Dashboard | Admin widget policies: free/default/mandatory/locked/disabled/conditional | UX / Administration | 009 | 020 | 009 FR-009..013; US3; SC-003 | Dashboard (009) | 020 | FULL |
| REQ-051 | Dashboard | Starter dashboard automatically configured during onboarding | UX | 009 | 002 | 009 FR-014; US4; SC-005 | Dashboard (009) | 002 | FULL |
| REQ-052 | Services/supervision | Service detail exposes state/uptime/errors/incidents/maintenance/sync/CPU/RAM/disk/temp/network/GPU/transcoding/ops per permissions | Integration / Security | 006 | 005, 025, 003 | 006 FR-010..018; US2/US6; SC-003/004 | Services & Health (006) | 005, 003 | FULL |
| REQ-053 | Data | External services remain source of truth; portal stores needed representation/history | Data | 005 | 007, 021, 024 | 005 FR-019..021; US6; 007 FR-015 | Connectors (005) | 007 | FULL |
| REQ-054 | Data | Disconnecting a service removes live access/sync but not portal history | Data | 005 | 021, 024 | 005 FR-025..028; US8; SC-005 | Connectors (005) | 021 | FULL |
| REQ-055 | Administration | Exactly one Admin account (no temporary delegation) | Security / Administration | 002 | 003, 020 | 002 FR-005/028..031; US8; 003 FR-009..012 | Permissions/Privacy (003) | 002 | FULL |
| REQ-056 | Administration | Admin domains: users/modules/plugins/connectors/services/content/support/gamification/marketplace/statistics/notifications/AI/appearance/security/audit/automations/portal-health | Administration | 020 | all domain specs | 020 FR-005/006; US2 + Domains Map | Administration (020) | all | FULL |
| REQ-057 | Product loop | action → Event → History → Statistics/Gamification/Community → AI/Achievements/Marketplace/Projects → Notifications → user → new action | Core Product | 007 | 013,017,012,010,018 | 007 US1/US3 (worked example); 024 worked example | Events & History (007) | 013,017,010 | FULL `[1]` |
| REQ-058 | Final definition | Holistic: environment visible, understandable, usable, interactive, continuously evolutive | Core Product | 001 | all | — (identity statement; verified holistically) | Portal Core (004) | all | FULL `[1]` |

### Footnotes
- `[1]` **Declarative / architectural requirement** (identity, scope boundary, cross-cutting set, product
  loop, final definition). Verified holistically across specs rather than by a single dedicated
  acceptance scenario. Counted in Acceptance-Criteria-gap metric (§8) as "no dedicated AC — by nature".
- `[2]` Module set is fully represented: Home→009, Media→024, Community→012, Statistics→017, Support→016,
  Marketplace→015, Services→006, News/Calendar→011, Administration→020. (News & Calendar share spec 011.)
- `[3]` Deterministic combination arithmetic resolved by **CD-024** (multiplicative + configurable cap).
- `[4]` **PARTIAL** — the lifecycle, reservation, refund-vs-consume ownership and "explicit published
  rules" are fully specified (015 FR-023..025; CD-008), but the **exact refund/consume formulas** are
  defaulted/deferred (OQ-56/70/71 in CANONICAL_DECISIONS §3). Non-blocking: product rule ("explicit
  published rules") is satisfied; only default values pending. Not CONFLICTING, not MISSING.
- `[5]` AI-diagnosis workflow owned by **Support (016 / CD-018)**; AI (018) references it (no competing
  workflow after the I1/D5 cleanup).
- `[6]` "Future push" is an explicitly deferred **channel** (not a spec gap); portal/email/sound are
  specified now.

## 2. Coverage Summary

| State | Count | Requirements |
|---|---|---|
| FULL | 57 | all except REQ-036 |
| PARTIAL | 1 | REQ-036 (reserved-funds formulas; default values pending) |
| MISSING | 0 | — |
| CONFLICTING | 0 | — |
| NOT_APPLICABLE | 0 | — |
| **Total** | **58** | REQ-001…REQ-058 |

### Quality-check metrics (traceability counts, not a score)
1. Blueprint requirements (atomic): **58**
2. FULL: **57**
3. PARTIAL: **1**
4. MISSING: **0**
5. CONFLICTING: **0**
6. NOT_APPLICABLE: **0**
7. Requirements without a canonical owner: **0**
8. Specifications with no incoming dependency: **2** — `026 i18n` (newest; consumers not yet citing it)
   and `020 Administration` (top-level governor). Expected, not blocking (see §7).
9. Requirements covered by multiple specifications: **56** (only REQ-023 and REQ-044 are single-spec)
10. Requirements with no dedicated acceptance criteria: **4** (REQ-002, REQ-004, REQ-057, REQ-058 —
    declarative/architectural, verified holistically; see §8)

## 3. Missing Requirements
**None.** The former HIGH gaps (Media, Observability) and the clarification gap (i18n) are closed by
specs 024, 025, 026. 0 MISSING.

## 4. Partial Requirements
- **REQ-036 (reserved funds refunded/consumed per published rules)** — PARTIAL. Lifecycle, ownership
  (CD-008), reservation, and "explicit published rules" are fully specified (015 FR-023..025). The exact
  refund/consume **formulas** are defaulted/deferred (OQ-56/70/71). **Non-blocking**: the product rule is
  satisfied; only default parameter values remain (admin/product config).

## 5. Conflicting Requirements
**None.** The sole prior text-level conflict (Notifications vs Automations WHEN/IF/THEN — I1) was
resolved by the CD-010 retro-propagation. 0 CONFLICTING.

## 6. Ownership Gaps
**None.** Every requirement maps to exactly one canonical owner from the approved ownership list. The
declarative/identity requirements (REQ-001/002/004/014/057/058) are owned by **Portal Core (004)** as the
shell/experience owner — a legitimate existing owner, not invented.

## 7. Dependency Gaps
- **DG-1 (Low, non-blocking)**: incoming references to **i18n (026)** are sparse — specs that render
  user-facing text/dates/numbers (008, 010, 011, 013, 015, 017, 024, 018) *are consumed by* i18n but do
  not yet *cite* 026 in their own dependency sections (026 post-dates them). Recommend adding a one-line
  reference to 026 in those specs' dependency sections. No behavior change.
- `020 Administration` having no incoming dependency is **expected** (it is the governor/Control Center;
  others depend on the *configuration mechanism* CD-011 which it owns, phrased via CD-011). Not a gap.
- No artificial dependencies were introduced; the enumerated chains (Marketplace→Gamification→Coins;
  Community→Marketplace→Funding; Events→Statistics/Gamification/Notifications/Automations;
  Connectors→Services→Events; i18n→Notifications/AI/Search/Marketplace/Statistics/Plugins;
  Permissions→AI/Search/Connectors/Administration/Community/Statistics) are all present and non-circular.

## 8. Acceptance Criteria Gaps
- **4 declarative requirements** (REQ-002 scope boundary, REQ-004 cross-cutting set, REQ-057 product loop,
  REQ-058 final definition) have **no single dedicated acceptance scenario** — by nature they are
  identity/architecture statements verified holistically across specs (REQ-057 is additionally evidenced
  by the worked examples in 007 and 024). **Not a coverage gap.** Optionally, a global end-to-end
  acceptance checklist could assert the product loop explicitly; not required for planning.
- All 54 behavioral requirements map to specs containing numbered acceptance scenarios (per the FR/US/AC
  column).

## Special Validation (explicit coverage confirmation)

| Item | Spec(s) | Canonical ref | Coverage |
|---|---|---|---|
| Media | 024 | — | FULL |
| Portal Observability | 025 | CD-020 | FULL |
| i18n | 026 | CD-023 | FULL |
| Configuration ownership | 020 | CD-011 | FULL |
| Automation ownership | 019 | CD-010 | FULL |
| Funding ownership | 015 | CD-008 | FULL |
| Event idempotence | 007 | CD-012 | FULL |
| Permissions | 003 | CD-002 | FULL |
| Privacy | 021 | CD-016 | FULL |
| Retention | 021, 025 | CD-016 | FULL |
| Source reconciliation | 005, 024 | CD-014/026 | FULL |
| Sensitive actions (audit) | 003, 007 | CD-013 | FULL |
| Infrastructure visibility (permission-gated) | 006 | CD-002 | FULL |
| Event modifiers | 014 | CD-024 | FULL |
| Statistics thresholds | 017 | — (admin config) | FULL |
| Versioning | 007, 013, 026 | CD-004/012 | FULL |
| Accessibility | 022 | CD-027 (WCAG 2.2 AA) | FULL |
| Responsive behavior | 004, 009, 022 | — | FULL |
| Import/export | 020 | — | FULL |
| Backup/restore | 020 | — | FULL |
| Installation/update | 020 | — | FULL |
| User deletion | 002, 021, 013 | CD-005/016 | FULL |
| Marketplace | 015 | CD-006 | FULL |
| Community Projects | 012, 015 | CD-007/008 | FULL |
| AI | 018 | CD-003 | FULL |
| Search | 008 | CD-017 | FULL |
| Notifications | 010 | CD-010 | FULL |
| Services/Health | 006 | CD-020 | FULL |
| Incidents | 016 (lifecycle), 006 (service-incidents) | CD-020 | FULL |
| Maintenance | 006, 011 (calendar) | — | FULL |
| Dashboard personalization | 009, 022 | — | FULL |
| Themes | 022 | CD-022 | FULL |
| Onboarding | 002, 009 | — | FULL |

All 33 special-validation items: **FULL**.

## 9. Recommended Corrections
- **RC-1 (Low, non-blocking)**: Fill REQ-036 reserved-funds refund/consume formulas (OQ-56/70/71) as
  admin/product config — pending default values only.
- **RC-2 (Low, non-blocking)**: Add incoming references to i18n (026) in the text-rendering specs (DG-1)
  for clean bidirectional cross-references.
- **RC-3 (Optional)**: Add a global end-to-end acceptance checklist asserting the product loop (REQ-057)
  if an explicit end-to-end test artifact is desired.

None of RC-1…RC-3 block technical planning.

## 10. Final Traceability Conclusion

- 58 atomic Blueprint requirements traced to specifications, FRs, user stories/acceptance scenarios,
  canonical owners, and cross-spec dependencies.
- **0 MISSING, 0 CONFLICTING, 0 ownership gaps.** 57 FULL, 1 PARTIAL (non-blocking default values).
- All 33 special-validation items FULL. All locked product decisions represented and non-contradicted.

**TRACEABILITY COMPLETE — READY FOR TECHNICAL PLANNING.**

(The single PARTIAL — REQ-036 default fund formulas — and the Low recommendations RC-1…RC-3 are
non-blocking follow-ups, not planning gates.)
