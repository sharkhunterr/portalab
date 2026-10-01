# Canonical Decisions Registry

**Created**: 2026-10-01
**Status**: Authoritative cross-spec reference. Produced by the global clarification pass.
**Scope**: Consolidates the locked product decisions, assigns a single owner to every cross-cutting
responsibility, and records the disposition of every open question (OQ-1…OQ-124) raised across specs
001–025. All specs MUST reference this registry instead of re-deciding these points.

> This registry does NOT redefine the product. It records decisions already made (Product Blueprint,
> Business Rules, Decisions, and the locked-decision block of the global clarification) and groups the
> remaining genuinely-open product choices in one place (see §4).

## 1. Ownership Map (one owner per responsibility)

| Responsibility | Owner spec | Consumers reference it |
|---|---|---|
| Identity, accounts, single-Admin lifecycle, Admin transfer | 002 Identity & Users | 003, 020 |
| Authorization engine (roles, permissions, groups, deny-by-default) | 003 Roles & Permissions | all |
| Shell, navigation, Command Palette, global states | 004 Portal Core | all UI |
| Connectors, capabilities, sync mechanics, source-of-truth at boundary | 005 Connectors | 006, 024 |
| Service state / availability / maintenance / service-incidents / service-sync | 006 Services & Health | 024, 025 |
| Event model, history, idempotency, **deduplication strategy**, reconstruction | 007 Events & History | all |
| Global Search + classic/AI parallelism | 008 Search & Command Palette | 018, 024 |
| Dashboard & widget framework | 009 Dashboard | 022, 024 |
| Notification/Alert/News/Email delivery, categories, channels | 010 Notifications | all |
| News, Wiki, Calendar content | 011 Content | — |
| Community: proposals, votes, participation | 012 Community | 015 |
| XP/Contribution/Coins, Levels, achievements/quests, reward engine, anti-abuse, **ledger** | 013 Gamification & Economy | 012, 014, 015, 024 |
| Campaigns (temporary themed context, modifiers) | 014 Campaigns | 013 |
| Marketplace + **community-funding lifecycle (owner)** | 015 Marketplace | 012, 013 |
| Support: tickets, feedback, **Incident lifecycle**, **AI-diagnosis workflow (owner)** | 016 Support | 006, 018, 025 |
| Statistics registry/engine (admin/portal-defined) | 017 Statistics | 009, 024 |
| AI capability (bounded by user permissions) | 018 AI | all |
| **Single generic WHEN/IF/THEN automation engine (owner)** | 019 Automations | 010, 025 |
| **Configuration system (owner)** + admin Control Center | 020 Administration | all |
| Visibility engine, privacy, retention, deletion/anonymization | 021 Privacy & Data Lifecycle | all |
| Presentation / personalization / themes / accessibility | 022 Personalization, Themes & A11y | all UI |
| Extension registry, plugin lifecycle, extension points, common observable model | 023 Extensibility | all |
| Media catalog, identity, playback, media history, requests, discovery | 024 Media | — |
| **Portal self-observation** (events/sync/automations/plugins/connectors/AI/perf/functional+technical health) | 025 Observability | 020 |
| i18n (language, translations, fallback, dates/times/timezones, numbers, plurals, regional formats) | 026 i18n | 008, 014, 017, 024, 018 |

**No-duplication rule (Constitution XX):** exactly one owner per mechanism. In particular: one incident
system (016), one monitoring/self-observation system (025), one automation engine (019), one
configuration system (020), one visibility engine (021), one event/dedup owner (007), one funding
lifecycle (015).

## 2. Canonical Decisions (CD) — reusable by all specs

These restate the locked decisions as cross-spec canon. Specs cite `CD-###`.

- **CD-001 (Admin singularity)**: exactly one Admin; other roles exist; no temporary delegation; Admin
  moves only via explicit transfer leaving exactly one Admin. (002/003/020)
- **CD-002 (Authz)**: server-side, deny-by-default; permissions never UI-only. (003)
- **CD-003 (AI rights)**: AI has exactly the invoking user's rights, never more, never a bypass;
  sensitive actions require appropriate confirmation. (018, all)
- **CD-004 (Three values)**: exactly XP, Contribution, Coins. Level is derived progression, not a
  currency. No inter-conversion unless an explicit, audited rule defines it (default: none). (013)
- **CD-005 (Coins nature)**: Coins are virtual/internal only; no real-money purchase; traceable
  transactions; balance normally never negative; refund = new transaction; destroyed (not refunded/
  transferred) at final account deletion. (013/015/021)
- **CD-006 (Marketplace basics)**: products may be free / Coins / level- / achievement- / campaign- /
  role-conditioned / combinations; already-owned permanent products not re-charged; Marketplace plugin
  activates immediately unless explicit config required; historical purchases never rewritten on price
  change; quotas purchasable; **no paid processing priority (incl. Seerr requests) ever**. (015)
- **CD-007 (Voting)**: every active account may vote; no minimum level; votes are free; funding is
  separate from voting and uses Coins; reserved funds held per the project lifecycle with explicit
  consume/refund rules. (012/015)
- **CD-008 (Funding lifecycle ownership)**: **Marketplace (015) owns** the lifecycle Idea → Proposal →
  Funding → Validation → Development → Beta → Release → Completion/Refund. **Community (012)** owns
  proposals/votes/participation. **Gamification/Economy (013)** owns Coins/ledger/transactions/
  reservations/debits/refunds. No competing implementations; others reference the Marketplace workflow.
- **CD-009 (Event vs Campaign vs Automation)**: a **Domain Event** = something that happened; a
  **Campaign** = a temporary themed context; an **Automation** = a configurable reaction. These three
  are distinct and never merged. (007/014/019)
- **CD-010 (Single automation engine)**: exactly one generic WHEN/IF/THEN engine, owned by **Automations
  (019)**. Notifications (010) has **no** second generic engine: configurable rules that send
  communications run as Automation actions; only product-mandated **system** notifications may be emitted
  directly. The engine prevents loops, uncontrolled repetition, and dangerous executions. (019/010)
- **CD-011 (Configuration)**: **Administration (020)** owns the configuration system; hierarchy is
  Global → Module → Plugin → User; modules/plugins declare settings into it (no private config engines);
  admin policy may constrain user preferences. (020, all)
- **CD-012 (Events/History)**: **Events & History (007)** owns the event model, history, idempotency, and
  dedup. `occurred_at` = real occurrence; `received_at` = portal receipt; `received_at` is never used
  alone as identity. **Dedup strategy**: (1) use a reliable source id when available; (2) else a
  deterministic key from event context; (3) never dedup on timestamp alone. Prevents double rewards /
  achievements / notifications / purchases / automation executions / event processing. Exact key form is
  an architecture decision. (007, all)
- **CD-013 (Audit)**: **Events & History (007) + Permissions (003)** own audit rules; Administration
  (020) only presents/uses them. Sensitive actions auditable with actor, action, timestamp, context, and
  result where relevant; audit is append-only. (all)
- **CD-014 (Source of truth)**: every datum has a source of truth; external services remain authoritative
  for native data; the portal keeps needed representations/history; disconnecting a service does not
  auto-delete portal history; a resync never destroys portal-native data. (005/021/024)
- **CD-015 (Synchronization)**: NO standalone Synchronization spec; sync is transversal, covered by
  Connectors (005) + Events & History (007) + Data Model + Privacy (021). New sync decisions respect
  these owners. (005/007)
- **CD-016 (Privacy & visibility)**: historized ≠ public. Visibility levels: Public, Community only,
  Leaderboards only, Private. User chooses when admin policy allows; admin may force visible/private/
  user-choice. A temporary admin override **preserves** the user's original preference (never overwrites)
  and **auto-restores** it when the override ends. (021, all)
- **CD-017 (Search + AI)**: classic search and AI run in parallel; classic results show immediately; AI
  continues in parallel; AI failure never blocks search; search failure never prevents AI from using its
  permitted sources. (008/018)
- **CD-018 (Support + AI)**: **Support (016)** owns the AI ticket-diagnosis workflow; **AI (018)**
  references it (does not redefine). (016/018)
- **CD-019 (Media independence)**: **Media (024)** is a domain independent of external services; Plex/
  RomM/Grimmory/Seerr/Radarr/Sonarr/etc. are sources/connectors, not the Media model. The catalog
  aggregates multiple sources; media events feed the existing transversal systems. (024/005)
- **CD-020 (Services/Health vs Observability)**: **Services & Health (006)** owns service state,
  availability, maintenance, service-incidents, service-sync. **Observability (025)** owns self-
  observation of the portal (events/sync/automations/plugins/connectors/AI/errors/performance + technical
  AND functional health). No two competing incident or monitoring systems. (006/025)
- **CD-021 (AI/MCParr)**: MCParr may be an access/action layer for compatible services but is **not** a
  mandatory functional dependency; the portal/AI remain fully functional without it. (018)
- **CD-022 (Theming vs Appearance)**: **Personalization/Themes/A11y (022)** owns presentation; themes
  change appearance only, never functional state/permissions/business-rules/source-of-truth; accessibility
  preferences override visual effects; critical info never hidden. Administration's "Appearance" only
  configures within policy. (022/020)
- **CD-023 (i18n)**: i18n is a dedicated transversal capability (its spec is to be created — §5 P1)
  covering interface language, content language, translations, fallback, dates/times/timezones, numbers,
  plurals, regional formats, admin-managed multilingual content, plugins, and AI. Recency/locale/timezone
  semantics (former OQ-36/66/81/109) belong here.
- **CD-024 (Reward-modifier combination)** [resolves PQ-1 / OQ-64/65/67]: overlapping XP/Coin/
  Contribution multipliers (reward rules + campaigns) combine **multiplicatively** (e.g., x2 · x1.5 = x3),
  deterministically, subject to a **configurable maximum total-boost cap**. Owner: Gamification (013);
  Campaigns (014) supplies modifiers; anti-abuse still applies. The cap value is admin config.
- **CD-025 (Authenticated-only portal)** [resolves PQ-2 / OQ-18/53]: the portal is **authenticated-only**;
  the only unauthenticated surface is sign-in. There is **no anonymous-internet audience**. Content
  audiences are expressed via the existing visibility tiers (Public = all members, Community,
  Leaderboards only, Private per CD-016) — "Public" means all authenticated members, not anonymous
  visitors. Owners: Portal Core (004) shell; Privacy (021) visibility; Content (011)/Community (012)
  audiences.
- **CD-026 (Cross-source conflict & identity)** [resolves PQ-3 / OQ-23/103/115/117/119]: content identity
  is matched by **reliable external ids first**, then metadata matching; field-level conflicts resolve by
  a **configured per-field source-of-truth priority**; **provenance is always preserved**. Consistent
  with CD-014. Owners: Connectors (005) at the boundary; Media (024) for media identity; Privacy (021)
  for reconciliation of user-linked data. Per-field priority tables are admin config.
- **CD-027 (Accessibility floor)** [resolves PQ-4 / OQ-105]: the accessibility floor is **WCAG 2.2 AA**,
  enforced regardless of theme/personalization (contrast, text size, focus, motion, keyboard/touch).
  Owner: Personalization/Themes/A11y (022); applies to all UI incl. plugin extensions.

## 3. Open-Question Disposition (OQ-1 … OQ-124)

Each OQ raised in specs 001–025 is dispositioned as: **RESOLVED** (by a CD above), **DEFAULT** (decided
by a sensible default consistent with the Blueprint, recorded here), **ARCH** (deferred to technical
architecture — not a product decision), or **PENDING** (genuine product choice, see §4).

### RESOLVED by canonical decisions
- OQ-1 Event/Campaign terminology → CD-009.
- OQ-3 Coin non-negativity → CD-005.
- OQ-4 / OQ-30 / OQ-31 idempotency/dedup key → CD-012.
- OQ-5 spec granularity → resolved (per-domain specs delivered).
- OQ-6 initial-Admin bootstrap → CD-001 + Administration first-run (020) establishes the sole Admin.
- OQ-9 Admin self-deletion/transfer → CD-001 (transfer-first; no delegation).
- OQ-11 custom role authorship → CD-001/CD-002 (Admin-owned; deny-by-default).
- OQ-17 nav ordering → CD-011 (admin config) + Dashboard personalization within policy.
- OQ-21 disconnection vs purge → CD-014 (disconnect ≠ delete; purge is a separate authorized action).
- OQ-32 reconstruction scope → CD-012 (Events owns; authorized/admin-triggered).
- OQ-34 event visibility default → CD-016 (historized ≠ public; default not-public/owner-only).
- OQ-35 AI scope in search → CD-003/CD-017 (bounded to permitted sources; parallel).
- OQ-55 project decision authority → CD-008 (Marketplace lifecycle + admin Validation gate).
- OQ-63 value inter-conversion → CD-004 (none unless explicit audited rule).
- OQ-78 feedback→contribution anti-abuse → CD-004 + Gamification anti-abuse (013).
- OQ-87 MCParr scope → CD-021 (optional; bounded by user permissions).
- OQ-94 AI-in-automation boundary → CD-003/CD-010 (AI assists non-critical; deterministic gate for
  critical).
- OQ-99 Appearance vs Theming → CD-022.
- OQ-36 / OQ-66 / OQ-81 / OQ-109 recency/locale/timezone/RTL → CD-023 (owned by i18n).

### DEFAULT (decided here, consistent with Blueprint; confirm at leisure, non-blocking)
- OQ-7 / OQ-33 / OQ-101 / OQ-122 retention & grace/dormancy durations → admin-configurable via CD-011;
  product defaults deferred to Administration config (not fixed in specs).
- OQ-8 display-name reuse after deletion → released and reusable; new account is a distinct identity with
  no inherited history.
- OQ-10 concurrent-session revocation → suspension/deletion revokes the user's other active sessions on
  next evaluation.
- OQ-12 group semantics → groups are permission-bearing; community grouping is a separate concern.
- OQ-13 explicit deny → supported; deny-by-default with optional explicit deny overriding grants.
- OQ-14 notable-denial audit threshold → audit all sensitive-action denials; others are admin policy.
- OQ-15 / OQ-29 infra permission granularity → single `infrastructure.read` baseline; finer per-metric
  gates optional later.
- OQ-16 keyboard-shortcut catalog → Design-System baseline; user remap optional (within CD-011).
- OQ-19 unauthorized vs not-found → do not leak existence where sensitive; otherwise "unauthorized".
- OQ-22 sync scheduling → per-connector admin config (CD-011/CD-015).
- OQ-24 discovery trust boundary → only operator-authorized targets; admin-confirmed candidates (005).
- OQ-25 / OQ-28 service-state thresholds & health-history granularity → admin config (CD-011).
- OQ-26 standard-user service fields → state + availability visible; uptime/last-error/infra require
  permission (CD-016/CD-002).
- OQ-37 / OQ-84 index vs live & freshness/caching → ARCH (see below) but staleness always marked.
- OQ-38 search-history retention → personal, Privacy-governed (021), user-clearable.
- OQ-39 / OQ-43 palette action & conditional-widget catalogs → extensible; baseline per owning specs.
- OQ-40 hide vs remove widget → hide retains config & is re-addable; remove takes it off the layout.
- OQ-42 Since-Last-Login scope → admin-configurable event set & lookback (CD-011).
- OQ-45 / OQ-48 / OQ-49 notification taxonomy, throttling, alert mute-bypass → admin config; critical
  alerts may bypass user mutes but never permissions; critical alerts never silently dropped.
- OQ-46 late/missed schedule evaluation → fire once if still relevant within the window; else skip;
  recorded.
- OQ-47 change/cancellation communications → send a corrective/cancellation communication.
- OQ-54 featuring precedence → admin-configurable max featured + priority.
- OQ-57 / OQ-62 challenges vs quests → "challenge" is a time-boxed quest variant (Gamification model).
- OQ-58 vote model → single up-vote of support per active account per project; retractable within policy.
- OQ-59 proposal permission → permissioned; moderated before becoming votable (Community + Admin).
- OQ-60 / OQ-67 / OQ-91 curves, boost caps, automation safety thresholds → admin config (CD-011).
- OQ-61 / OQ-120 / OQ-121 anomaly handling & escalation → default: withhold/flag + explicit escalation
  rule to Incident (016); thresholds admin-config.
- OQ-68 condition matching → tag/genre/attribute-based, deterministic (case-insensitive, defined
  semantics).
- OQ-69 manual campaign override precedence → manual override takes precedence over schedule and is
  recorded; clears back to schedule.
- OQ-72 quota semantics → defined by the relevant request service/connector; Marketplace only sells
  quota (CD-006).
- OQ-73 revocation grounds → defined, audited grounds (abuse, grant expiry, policy); never arbitrary.
- OQ-74 combined conditions → AND by default; OR/any-of groupings may be added later.
- OQ-75 ticket workflows → admin-definable per type; product provides a sensible baseline.
- OQ-77 attachment policy → validated/sanitized; type/size limits are admin/security config.
- OQ-79 incident↔ticket linking → agents may link/merge duplicates to an incident per policy.
- OQ-80 statistics authorship → Admin/portal defines; plugins may declare definitions within policy
  (CD-002/CD-011); users never author (017).
- OQ-82 / OQ-102 privacy-safe aggregation → minimum-sample/anonymization required (CD-016); threshold is
  admin config.
- OQ-83 unlock re-lock → a time-bound unlock (campaign) re-locks when it ends unless another condition
  keeps it unlocked.
- OQ-88 source-attribution granularity → per-answer source list; interpretation marked distinctly (CD-003).
- OQ-89 AI action audit detail → per CD-013 (actor=user, channel=AI, action, time, context, result); no
  PII/secret leakage.
- OQ-90 automation time triggers → bounded relative/recurring schedules, not arbitrary cron.
- OQ-95 required-actions model → derived from component health/incidents; prioritized action-first (025).
- OQ-98 first-run/reset safeguards → first-run not trivially re-runnable; any reset is explicit + audited.
- OQ-106 device vs account preferences → account-level follows the user; device-specific layout handled
  sensibly.
- OQ-107 preference migration on update → map to nearest/default; never a silent reset.
- OQ-114 plugin data ownership → the plugin owns its data; references to core objects handled on removal
  per policy (CD-016/021).

### ARCH (deferred to technical architecture — not product decisions)
OQ-37, OQ-41, OQ-44, OQ-51 (safe-render standard), OQ-84, OQ-85 (provider abstraction), OQ-96, OQ-97,
OQ-104 (anonymization irreversibility mechanics), OQ-108 (theme sandbox), OQ-110 (plugin isolation),
OQ-112 (update delivery/rollback), OQ-124 (observability storage vs backbone).

### PENDING — genuine product choices (see §4)
OQ-64/OQ-65 (modifier combination) · OQ-18/OQ-53 (public surface & content audience) ·
OQ-23/OQ-103/OQ-115/OQ-117/OQ-119 (source-of-truth conflict & media identity) · OQ-105 (accessibility
conformance target). Plus lower-impact confirmations: OQ-52 (wiki concurrent editing), OQ-56/OQ-70/OQ-71
(refund/funding formulas), OQ-76/OQ-123 (support vs admin observability split), OQ-93 (automation
authoring scope), OQ-111 (plugin trust/review), OQ-116 (media "finished" thresholds), OQ-118
(recommendations ownership).

## 4. Pending Canonical Questions (4) — ✅ ALL RESOLVED (2026-10-01)

All four have been answered and folded into canonical decisions:

- **PQ-1 → CD-024** (multiplicative + configurable cap).
- **PQ-2 → CD-025** (authenticated-only; "Public" = all members, no anonymous tier).
- **PQ-3 → CD-026** (external-id-first matching + per-field source-of-truth priority + preserve
  provenance).
- **PQ-4 → CD-027** (WCAG 2.2 AA floor).

Lower-impact PENDING items in §3 remain **defaulted** (non-blocking); confirm at leisure:
OQ-52 (wiki concurrent editing), OQ-56/70/71 (refund/funding formulas), OQ-76/123 (support vs admin
observability split), OQ-93 (automation authoring scope), OQ-111 (plugin trust/review), OQ-116 (media
"finished" thresholds), OQ-118 (recommendations ownership — default: Statistics provides data, AI may
enrich, per CD-003/017).

## 5. Residual Problems (by priority)

### HIGH
- **P1 — i18n spec missing (missing ownership)** — ✅ **RESOLVED (2026-10-01)**. Created `specs/026-i18n`
  owning CD-023; OQ-36/66/81/109 are now anchored there. New i18n-specific open items: OQ-125 (RTL
  language set), OQ-126 (baseline languages/defaults), OQ-127 (translation workflow), OQ-128 (wall-clock
  vs absolute scheduling default), OQ-129 (unknown-language handling default).

### MEDIUM
- **P2 — Notifications WHEN/IF/THEN framing (contradiction, now RESOLVED by CD-010)**. Spec 010
  describes a WHEN/IF/THEN engine for communications. Per CD-010 there is only ONE engine (Automations
  019). **Resolution**: retro-propagate — 010 keeps delivery/categories/channels/system notifications;
  configurable rules run as Automation actions. (Edit note, not a rule change.)
- **P3 — Funding lifecycle described in 012/013/015 (duplication, now RESOLVED by CD-008)**.
  **Resolution**: 015 is the owner; 012/013 reference the Marketplace workflow. Retro-propagate ownership
  note.
- **P4 — Configuration asserted without owner (now RESOLVED by CD-011)**. Specs 002/009/020/021/022
  assert the hierarchy. **Resolution**: 020 owns; others reference CD-011.
- **P5 — PENDING product choices PQ-1…PQ-4** (see §4): need answers before dependent detailed design.

### LOW
- **P6 — Stale "future spec" references**. Privacy(021)/Theming(022)/Extension Registry(023)/
  Observability(025)/Media(024) now exist; specs 003/004/006/008/012/014/015/017/020 still say "future".
  **Resolution**: refresh cross-references to the real spec numbers.
- **P7 — OQ-1 resolved but not marked in 001/007**. **Resolution**: mark resolved, cite CD-009.
- **P8 — AI 8-step diagnosis flow duplicated in 016 & 018**. **Resolution**: 016 authoritative (CD-018);
  018 references.
- **P9 — Minor DEFAULT items in §3** may be confirmed at leisure; none blocking.

## 6. Verification Summary

- **Contradictions with Product Blueprint / Decisions**: none. The locked decisions confirm the specs;
  P2/P3/P4 were ownership/duplication ambiguities now resolved by CD-008/010/011 (retro-propagation
  pending, no rule change).
- **Every domain has a clear functional owner**: yes (see §1) — except **i18n (P1)**.
- **One definition per transversal mechanism**: yes after CD-008/010/011/012/016/020 (funding, automation
  engine, configuration, events/dedup, visibility, incidents/observability).
- **Blueprint rules propagated**: yes; CD-001…CD-023 restate them for reuse.
- **Open decisions consolidated in one place**: yes (this registry, §3–§4).
- **Ready for planning**: PQ-1…PQ-4 resolved (CD-024…CD-027); **P1 (i18n spec) resolved** (026). No
  structural blockers remain. Optional remaining work: retro-propagation of P2/P3/P4/P6/P7/P8 (reference
  edits, no rule changes) to tidy cross-references; and confirming the §3 DEFAULT items + i18n OQ-125…129
  at leisure. The project is **planning-ready**.

