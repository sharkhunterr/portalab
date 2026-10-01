# Implementation Plan: Media

**Branch**: `024-media` | **Date**: 2026-10-01 | **Spec**: `specs/024-media/spec.md`
**Roadmap**: Phase 5 step 16 *Media*. First domain module on top of the core: consumes 005 (connectors), 006 (health), 007 (events), 008 (search SDK), 009 (widgets), 010 (categories), 017 (statistics packs), 021 (visibility), 022/004 (UI).

## Summary
Module `media` provides the unified, **service-independent catalog**: Media Objects with stable identity (id-first matching, reversible merge/split), per-field provenance and source priority, normalized source-agnostic playback sessions and history (event stream as the record), requests mirrored from request services with quota, discovery shelves, an extensible detail page whose sections load and fail independently, and strict separation of availability / service health / sync state. It contains **no provider-specific code** (capabilities only) and introduces the media capability catalog (`media.library`, `media.playback`, `request.service`) that connectors implement.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `Pillow` (already via 002) for image re-encoding · **Storage**: schema `media`; images via `core.blobstore` · **Testing**: pytest real PG + fake connectors (conformance kits), Vitest, Playwright + axe · **Constraints**: no mandatory provider; outage never removes catalog entries; progress events throttled; personal history private by default; no secrets/source URLs to clients · **Scale**: personal/community libraries up to ~10⁵ objects, ~10⁶ history entries.

## Constitution Check — PASS
I/II capability decoupling, source of truth (CD-014/026) · III extensible types/blocks/connectors · IV event-driven, idempotent · V provenance per field · VI/VII permission and privacy (history Private by default) · IX isolation/degraded states, distinct availability/health/sync · XI/XII states, accessibility · XX no second search/stat/notification/reward engine. No violations.

## 1. Architecture
```
Connectors (005) ─ media.library sync ─▶ RecordSink ─▶ source_items ─▶ IdentityResolver(id-first; fuzzy→candidates) ─▶ media.objects/external_ids
                                                         └▶ FieldResolver(candidates + priority + admin override) ─▶ effective + provenance ; images→blobstore
media.playback (live) ─▶ PlaybackPoller job ─▶ normalize ─▶ playback_sessions ─▶ events(007) ─▶ HistoryProjection ─▶ history_entries/user_progress
request.service ─ submit/status/sync ─▶ RequestService (quota via own RequestQuotaService; units sold by 015) ─▶ media.requests
Read side: Catalog API · Detail sections (independent) · Discovery shelves · providers (Search/Widgets/Stats/AI tools)
Availability ⟂ service_state (006) ⟂ sync_state (005) returned side by side
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `MediaTypeRegistry` | extensible kinds, hierarchy, thresholds | capability registry | `register_media_type` | no core change per type | registry tests |
| `LibrarySink` (RecordSink) | idempotent upsert/deactivate of source items | 005 | `upsert/deactivate` | never deletes; sanitized payload | sink contract tests |
| `IdentityResolver` | id-first match, candidates, merge/split | `core.db` | internal + admin API | reversible, audited | matching/merge tests |
| `FieldResolver` | per-field priority + admin override + provenance | 020 config | `resolve(object)` | deterministic | priority matrix tests |
| `ImageService` | fetch via connector client, validate/re-encode, serve | blobstore | API | no source URL/token exposure | image tests |
| `AvailabilityService` | object availability + service state + sync state (separate facts) | 005/006 | `status(object)` | never collapse | degraded-mode tests |
| `PlaybackPoller` + `SessionNormalizer` | poll, normalize, throttle events, stale/interrupt | `media.playback`, jobs | job | bounded rate; source loss ⇒ stale | session lifecycle tests |
| `UserLinkService` | user↔service identity mapping | identity | API | verified/unlinked handling | link tests |
| `HistoryProjection` | events → history/progress, finished thresholds, reconciliation | 007 consumers | `@consumer` | idempotent, `occurred_at`, finished sticky | replay tests |
| `RequestService` | submit/mirror/cancel, quota, state normalization | `request.service`, 015 port | API | no paid priority; idempotent | request tests |
| `Discovery` + `RecommendationProvider` | shelves | 017, history | API | permission/privacy bounded | shelf tests |
| `DetailSections` + slot registry | independent sections (info, sources/availability, history, progress, requests, people, statistics, associated events, actions, external links) + plugin blocks | 022/004 | API/UI | each section own state | isolation tests |
| Integrations | Search/widgets/stats packs/notification categories/AI tools/palette | 008/009/017/010/018 | registrations | thin | contract tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/media-contracts.md`

## 5. Events
Produced (007 envelope, ids/counters only): `media.added|updated|removed`, `media.availability_changed`, `media.merged|split` (portal-native identity events), `media.playback_started|progressed|paused|finished|abandoned|error` (resume ⇒ `progressed`; session ended at/above the finished threshold ⇒ `finished`, below ⇒ `abandoned`; source lost ⇒ `error`), `media.resume_available`, `media.request_created|updated|available` — names as listed in spec 024 / EVENT_MODEL. Consumers (013 rewards, 014 campaigns, 017 stats, 010 notifications, 018, 019) idempotent via dedup keys `(session_key, state_seq)`, `(session_key, 'finished')`, `(request_id, state)`. Progress throttled to state change or ≥ 60 s. Ordering: by `occurred_at`; late events never revert *finished*. Consumed: `service.status_changed`, erasure participant calls.

## 6. Permissions & Security
`media.read` (default grant) + visibility per datum class (021) for personal sections; `media.request` (default grant, quota-bound); `media.manage` Admin-only (merge/split/override/matching; sensitive actions confirmed + audited). Destructive actions on source services are **not provided** in this plan (would require `media.source.delete`, sensitive + confirmation). User links verified where the service supports it; unlinked activity never attributed. Source payloads sanitized (no tokens/URLs with credentials); images proxied; external text escaped.

## 7. Configuration — `data-model.md` (declared into 020; `media.fieldPriority.*` shape is the one consumed by 005).

## 8. External Integrations
Only through capabilities/connectors. Reference connectors (Plex/Jellyfin, Radarr/Sonarr, Seerr, Grimmory, RomM, …) are separate connector implementations delivered later via 005's SDK + this plan's conformance kits; none is required.

## 9. Error Handling & Resilience
Source outage ⇒ section `unavailable`/`stale` with `as_of`, catalog intact · sync error ⇒ shown as sync state, last good data retained · poll failure ⇒ sessions `stale` then `interrupted` (`media.playback_error`) · duplicate source records ⇒ idempotent upsert · identity conflict ⇒ candidate queue, no auto-merge · missing user link ⇒ unlinked, not attributed · quota exceeded ⇒ 429-class problem · image fetch failure ⇒ placeholder · replay/duplicates ⇒ no double history/rewards.

## 10. Observability
Per-service poll/sync lag, unresolved/unlinked counts, candidate queue size, match/merge counts, request failures, section latency; registers `media` with 025 (functional: catalog freshness per service, playback poll health).

## 11. Testing Strategy
Capability conformance kits (fake `media.library|playback|request.service`). Unit: field priority matrix, finished thresholds, reconciliation, session normalization/throttling. Integration (real PG): two sources one object; removal/outage invariants; merge/split reversibility; history projection replay equality; privacy of history/concerned users; request quota/no-paid-priority; sections isolation under one failing source. Frontend: detail sections independent states, shelves, request flow, accessibility under themes. E2E: link account → playback → continue-watching → finished.

## 12. Migration / Versioning
Alembic revision for `media`; capability Protocols and `SourceRecord` schemas semver'd; new media types are additive registry entries; effective-field rebuild job after priority changes (audited).

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002/003, 005 (sinks, capability mechanism), 006 (health), 007, 020, 021 (visibility datum classes `media_history`, `media_request`), 022/004. Consumes optionally: 015 (credits quota units through `RequestQuotaService.add_units`), 013/014 (via events), 018 (tools). Exposes: `MediaCatalog`/`HistoryReader` to 012, 013, 014, 017, 018, 019; slot registry to 023. Connectors for concrete services are separate deliverables.

## 14. Implementation Phases
1 Capabilities, schema, type registry → 2 Library sink + identity + field resolution → 3 Catalog API + detail page sections → 4 Availability/degraded modes → 5 Playback poller/sessions/events → 6 History projection + progress + finished → 7 Requests → 8 Discovery + providers (search, widgets, stats, notifications, AI) → 9 Admin matching/merge/overrides → 10 Extensibility slots + hardening.

## 15. Technical Decisions — `research.md` R1–R15.

## 16. Risks / Open Technical Questions
- **R1** OQ-115..119 use plan defaults (research); **product confirmation requested** (matching policy, thresholds, reconciliation, recommendation ownership, field priority defaults).
- **R2** Polling-based playback is approximate; webhooks may be added per connector later (contract unchanged).
- **R3** History volume: projection table partitioning by year when needed; progress throttling keeps events bounded.
- **R4** Fuzzy match candidates need an admin workflow; backlog size visible in observability.
- **R5** Concrete connectors are outside this plan; the conformance kits make them independently deliverable.
- **R6** People/credits kept as tags (no person entity) in v1.

## Project Structure
```text
backend/src/portalab/{capabilities/{media,media_core}, modules/media/{types,sink,identity,fields,images,availability,playback,links,history,requests,discovery,sections,providers,api,models}} · backend/migrations/media/versions/
frontend/src/features/media/{home,catalog,detail,playback,requests,links,admin}
```
