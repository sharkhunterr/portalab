# Cross-plan obligations (pre-implementation audit, 2026-10-01)

Obligations that one plan needs from another plan. Each one is either **fixed** directly in the plans during the
audit, or **scheduled** as a task in the owning spec's `tasks.md` under the heading
"Cross-spec obligations (audit 2026-10-01)". Decisions taken during the audit are CD-028…CD-035 in
`decisions/CANONICAL_DECISIONS.md`.

| # | Owner | Raised by | Obligation | Status |
|---|---|---|---|---|
| F1 | 006 / 010 | 010 | Maintenance events aligned: 006 emits `maintenance.scheduled\|rescheduled\|started\|ended\|cancelled` with `schedule_version`; 010 consumes those names | Fixed in plans |
| F2 | 007 | 013, 017, 019 | Event-type registry annotations `rewardable` / `aggregatable` / `automatable`, `provenance.automation`, `actor_kind` ai/automation | Task in 007 |
| F3 | 013 | 015 | Coin reservations (`reserve/release/consume`) + unit-of-work-aware `spend/refund/reserve` | Task in 013 (+ data model/contracts) |
| F4 | 013 | 019 | `grant_via_automation` + award action types | Task in 013 |
| F5 | 013 | 014 | `DefinitionSource` for campaign-scoped achievements/quests | Task in 013 |
| F6 | 024 | 014, 019 | Media `ActivityAttributeProvider` | Task in 024 |
| F7 | 005 | 024 | Per-field priority shape `media.fieldPriority.<kind>.<field>` | Fixed in 005 plan + task |
| F8 | 022 | 014, 015 | `ui.campaignThemes`, campaign overlay, theme entitlements | Task in 022 (+ data model) |
| F9 | 009 | 015 | Widget catalog filtered by `EntitlementReader` | Task in 009 |
| F10 | 016 | 011 | Reuse the shared upload helper | Task in 016 |
| F11 | 016 | 019 | Ticket/incident creation for non-interactive principals + action types | Task in 016 |
| F12 | 018 | 019 | Read-only `ai.invoke` facade | Task in 018 |
| F13 | 011 | 019 | `content.publish` action type | Task in 011 |
| F14 | 005 | 019 | `connector.sync` / `connector.action` action types | Task in 005 |
| F15 | 003 | 011, 015, 016, 023 | `declare_permission(default_roles)`, plugin-scoped and allow-listed grants, principal channels | Task in 003 |
| F16 | — | — | (withdrawn: `events.manage` = 007 event store, `campaigns.manage` = 014, both per the 003 catalog) | Closed |
| F17 | 004 | 008, 011 | Command `sensitivity`, help-entry slot | Task in 004 |
| F18 | 020 | 009, 023 | Dynamic setting validation, `ModuleRegistry` delegation, plugin-scope settings | Task in 020 |
| F19 | 021 | 012, 013, 023 | `register_datum_class` + plugin erasure participant enforcement | Task in 021 |
| F20 | all registry owners | 023 | Owner-tagged `register`/`unregister(owner)` for the conformance sweep | Tasks in 003, 004, 005, 007, 008, 009, 010, 011, 012, 015, 017, 018, 019, 020, 022, 024, 026 |
| F21 | 002 / 009 | 009 | Onboarding `dashboard` step content delivered by 009 | Already in plans |
| F22 | 012 / 015 | 012 | Community slice D ships with Marketplace slice A (roadmap step 25) | Process (roadmap) |

## Also fixed during the audit (no task needed)
- Media event names aligned with spec 024 / EVENT_MODEL (`media.added|updated|removed`, `media.availability_changed`, `media.playback_started|progressed|paused|finished|abandoned|error`, `media.resume_available`, `media.request_created|updated|available`).
- `service.state_changed` → `service.status_changed` (004, 010, 024); 004 consumes `permission.*` (003) and `admin.module_toggled|plugin_toggled` (020).
- Media detail page sections completed (statistics, associated events, actions, external links).
- Feedback conversion targets = Community proposals (`kind=feature|project`) per CD-008.
- Home widgets `community.projects` (012) and `marketplace.featured` (015) added (REQ-018).
- Privacy center `/me/privacy` added to 021 (user journey "Data Center").
- Quota accounting moved to Media (CD-034); economy anomaly escalation to Incident (OQ-61 default).
- 020 user stories US2/US3/US8 covered; task labels fixed (002, 006, 010, 020); missing file paths added.
- 016 incident notifications use the `notifications.send` stub until 010 (roadmap step 13 < 15).
