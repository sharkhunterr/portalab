# Feature Specification: Media

**Feature Branch**: `024-media`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Complete functional specification of the portal's Media module — unified catalog, detail, playback, history, requests, discovery; integrating existing engines without re-defining them."

## Role of This Document

This is a **detailed feature specification** for the Media module — the unified, service-agnostic media
experience (catalog, detail, playback, history, requests, discovery) that aggregates many source
services via capabilities and feeds the portal's cross-cutting engines. It conforms to and refines the
superior reference specification (`specs/001-portal-global-spec/spec.md`) and **composes with** Connectors
(`005`), Services & Health (`006`), Events & History (`007`), Search & Command Palette (`008`), Dashboard
(`009`), Notifications (`010`), Community (`012`), Gamification & Economy (`013`), Campaigns (`014`),
Marketplace (`015`), Statistics (`017`), AI (`018`), Automations (`019`), Privacy (`021`), and
Extensibility (`023`), under the project Constitution (`.specify/memory/constitution.md`, v1.0.0). It
draws on `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `product/GLOSSARY.md`,
`architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`, and `architecture/DATA_MODEL.md`.

### What this spec OWNS vs CONSUMES (normative — no duplication, principle XX)

- **OWNS**: the unified media catalog + **service-independent content identity**, media types (extensible),
  the media **detail page** (extensible), the **playback/session** concept (source-agnostic), the **media
  history** model, the **request representation**, media **discovery** surfaces, the media **object model**,
  and the **media domain events** it produces.
- **CONSUMES (does not re-define)**: source aggregation / sync / disconnection semantics → **Connectors
  (005)**; availability vs service-health vs sync-state distinctions → **Services & Health (006)**; the
  event/history backbone, `occurred_at`/`received_at`, idempotency → **Events & History (007)**; global
  search → **Search (008)**; widgets → **Dashboard (009)**; notification delivery → **Notifications (010)**;
  rewards/anti-abuse/ledger → **Gamification & Economy (013)**; campaign modifiers → **Campaigns (014)**;
  request quota + no-paid-priority → **Marketplace (015)**; statistics definitions/engine → **Statistics
  (017)**; AI access within permissions → **AI (018)**; visibility levels + personal-history-not-public →
  **Privacy (021)**; plugin extension points → **Extensibility (023)**.

**Non-goal**: Media MUST NOT be a mere Plex frontend. The Core Media MUST NOT be designed around any
single provider; no source service is ever assumed mandatory.

**Terminology** (Glossary + prior specs): Media Object = service-independent content identity; Source =
an external service providing data about a media item via a capability; Playback Session = a
source-agnostic representation of a play/read/game session; Domain Event = a recorded fact;
`occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified catalog with service-independent content identity (Priority: P1)

A user browses one unified catalog where a given title (film, series, episode, book, game, extensible
types) has a single portal identity even when several source services describe it; sources are shown as
provenance, not as separate duplicate entries.

**Why this priority**: The unified, service-independent identity is the defining value of Media and what
makes it "an experience layer, not a Plex frontend".

**Independent Test**: Register two sources describing the same title (e.g., a library service and a
request service); browse the catalog; confirm one Media Object appears with both sources listed as
provenance, metadata merged per rules, and no duplicate entries.

**Acceptance Scenarios**:

1. **Given** the same content described by multiple sources, **When** the catalog is viewed, **Then** it
   appears as a single Media Object with its sources listed as provenance (not duplicated).
2. **Given** a Media Object, **When** viewed, **Then** it exposes metadata, posters/images, genres, tags,
   people, dates, durations, status, availability, and provenance.
3. **Given** a new media **type** (beyond film/series/episode/book/game) is introduced via extension,
   **When** added, **Then** it integrates into the catalog model without redesigning the Core.
4. **Given** content identity, **When** resolved, **Then** it is independent of any source service (a
   source disappearing does not change the content's identity).

### User Story 2 - Aggregate source services via capabilities (no mandatory provider) (Priority: P1)

An admin connects source services (e.g., Plex, Radarr, Sonarr, Seerr, Grimmory, RomM, future connectors);
Media consumes them **through capabilities** (per Connectors 005), never by hard-coded service identity,
and the Core never depends on any one provider.

**Why this priority**: Capability-based aggregation is the locked architecture principle that lets Media
grow and survive a provider being absent or down.

**Independent Test**: Provide a capability (e.g., "library catalog", "playback state", "request") via two
different services; confirm Media works with either; remove all providers of a capability and confirm
Media degrades gracefully (not a crash).

**Acceptance Scenarios**:

1. **Given** a capability provided by a source, **When** Media uses it, **Then** it does so via the
   capability contract (Connectors 005), not a service name.
2. **Given** two services providing the same capability, **When** either is connected, **Then** Media
   functions with either, merging per provenance rules.
3. **Given** no service provides a required capability, **When** a dependent surface is viewed, **Then** it
   shows a distinguishable unavailable/no-data state (per Services & Health 006) and the rest of Media
   stays usable.

### User Story 3 - Extensible media detail page (Priority: P1)

A user opens a media detail page showing principal info, availability, sources, history, progression,
permitted concerned users, relevant statistics, associated events, optional recommendations, available
actions, external-service links, and plugin-contributed blocks — each section loading independently and
permission/privacy bounded.

**Why this priority**: The detail page is where the whole portal converges on one object; it must be
extensible and resilient without leaking data.

**Independent Test**: Open a media detail page with several sources and prior activity; confirm each
section renders (with its own functional state), that statistics come from Statistics (017), that a plugin
block appears via the extension point, and that unpermitted/private data is not shown.

**Acceptance Scenarios**:

1. **Given** a media item, **When** its detail page loads, **Then** it presents principal info,
   availability, sources, history, progression, relevant statistics, associated events, actions, external
   links, and any plugin blocks — each section with its own functional state.
2. **Given** a slow/unavailable source for one section, **When** the page loads, **Then** that section
   shows its state while the rest of the page remains usable (degraded mode per 006).
3. **Given** "concerned users" (e.g., who watched), **When** shown, **Then** they respect each user's
   visibility/privacy (per Privacy 021) — personal activity never public by permission alone.
4. **Given** a plugin page-block extension, **When** present, **Then** it integrates via the extension
   point (Extensibility 023), uses the Design System, and is permission/privacy bounded.

### User Story 4 - Source-agnostic playback / current activity (Priority: P1)

The portal represents a current play/read/game session independently of the source service: current
playback, pause, progression, duration, user, media, source, device (if available), session start/end —
working across multiple sources without the Core depending on Plex.

**Why this priority**: "Current playback" is an explicit Home/Media capability and the clearest expression
of source-agnostic design.

**Independent Test**: Start a session on one source and (separately) on another; confirm the portal shows
each as a current Playback Session with the common fields, that pause/progress update, and that session
start/end produce events — with no Core coupling to a specific service.

**Acceptance Scenarios**:

1. **Given** a session on any source, **When** it is active, **Then** the portal represents current
   playback with user, media, source, progression, duration, device (if available), and start time.
2. **Given** a session, **When** it pauses/progresses/ends, **Then** the portal reflects the state and
   emits `media.playback_started` / updates / `media.playback_finished` (or abandoned) events with real
   `occurred_at`.
3. **Given** playback from different sources, **When** represented, **Then** the model is uniform and the
   Core does not depend on any single service (Plex is not required).
4. **Given** the source is unavailable mid-session, **When** it happens, **Then** the session shows a
   degraded/stale state rather than disappearing or being treated as finished incorrectly.

### User Story 5 - Media history feeding the backbone (Priority: P1)

Media history records play/read/game sessions, finished viewing, progression, resume points, abandoned
plays, repeated plays, consultation history, provenance, and real timestamps — and feeds Statistics, XP,
Contribution, Achievements, Campaigns, Community activity, and Notifications **only via the existing event
system**.

**Why this priority**: History is the memory that powers the product loop; it must use the event backbone
(007) and the reward engine (013), not parallel mechanisms.

**Independent Test**: Complete, abandon, resume, and repeat media; confirm each is historized with
provenance and real `occurred_at`, and that downstream reactions (a statistic, an XP grant) occur via the
event system idempotently.

**Acceptance Scenarios**:

1. **Given** media activity (finished/abandoned/resumed/repeated/consulted), **When** it occurs, **Then**
   it is recorded in media history with provenance and real `occurred_at` (distinct from `received_at`).
2. **Given** a media history event, **When** published, **Then** Statistics/XP/Contribution/Achievements/
   Campaigns/Community/Notifications react **via the event backbone (007)** and reward engine (013) — no
   parallel reward or stat logic.
3. **Given** duplicate/late delivery of a media event, **When** processed, **Then** the outcome is
   idempotent (no double XP/stat), per 007's dedup rule.
4. **Given** personal media history, **When** stored, **Then** it is not public by default (Privacy 021).

### User Story 6 - Media requests (integrating request services) (Priority: P2)

The portal represents requests from existing request services: request, requester, requested media,
state, progression, availability, and history — and honors the locked rule that Coins may buy extra
request **quota** but never processing **priority**.

**Why this priority**: Requests connect Media to Marketplace/economy and are explicitly in scope; the
no-paid-priority rule is locked.

**Independent Test**: Create a request via a request-capability source; track its state/progression to
availability; purchase extra quota with Coins (via Marketplace 015) and confirm quota increases but no
priority option exists.

**Acceptance Scenarios**:

1. **Given** a request-capability source, **When** a user requests media, **Then** the portal represents
   the request (requester, media, state, progression, availability, history).
2. **Given** a request's lifecycle, **When** its state changes at the source, **Then** the portal
   reconciles it per source-of-truth rules (005) and MAY notify per preferences (010).
3. **Given** request quota, **When** more is purchased with Coins, **Then** quota increases via a traceable
   transaction (013/015) and **no** paid processing priority exists or is offered.

### User Story 7 - Media search & discovery via existing engines (Priority: P2)

The catalog is searchable through global Search (008) with media-relevant filters/sort/categories, and
Discovery surfaces new/recently-added/recently-watched/continue-watching/recommendations/popular/related/
event-linked content — all permission/privacy bounded, without imposing a recommendation algorithm.

**Why this priority**: Search/Discovery turn the catalog into something explorable and reinforce the
one-environment feel; they must reuse Search (008) and Statistics (017), not a parallel engine.

**Independent Test**: Search media with filters (type/genre/availability/source); view each Discovery
surface; confirm results are permission/privacy bounded, "continue watching" uses resume points, and
event-linked content reflects an active Campaign (014).

**Acceptance Scenarios**:

1. **Given** media content, **When** searched via global Search, **Then** permitted media results appear
   grouped by type with filters (type, genre, availability, source, and user where permitted) and sort.
2. **Given** Discovery, **When** viewed, **Then** it surfaces new/recently-added/recently-watched/continue-
   watching/popular/related/event-linked content within permissions/privacy.
3. **Given** "continue watching", **When** shown, **Then** it uses the user's resume points from media
   history and respects privacy.
4. **Given** recommendations, **When** shown, **Then** the spec requires the data/surfaces but imposes no
   specific algorithm (AI/Statistics may power it per their specs).

### User Story 8 - Media + AI within permissions (Priority: P2)

The AI can exploit the media data the user may access (catalog, history, progression, availability,
requests, statistics) to answer questions like "what did I watch this week?", "which sci-fi was added
recently?", "where am I in this series?", "why isn't this film available?" — strictly within the user's
permissions.

**Why this priority**: Media is a prime AI use case; it must reuse AI (018) and never exceed the user's
permissions.

**Independent Test**: Ask the AI each example question as users with different permissions; confirm
answers use only permitted media data, cite sources where relevant, and never reveal others' private
history.

**Acceptance Scenarios**:

1. **Given** permitted media data, **When** the user asks a media question, **Then** the AI answers using
   only what the user may access (per AI 018), citing sources where relevant.
2. **Given** "why isn't this film available?", **When** asked, **Then** the AI explains using availability/
   source-health/sync state (distinguishing media-unavailable vs service-unavailable vs sync-error).
3. **Given** another user's private history, **When** anyone asks, **Then** the AI does not reveal it
   (permission + privacy bounded).

### User Story 9 - Media + Community within privacy (Priority: P3)

Authorized community features may reference media (activity, projects, events, recommendations,
statistics, challenges) while strictly respecting each user's visibility/privacy.

**Why this priority**: Community references to media enrich participation but must not leak private
viewing data.

**Independent Test**: Surface media in a community activity/leaderboard/challenge; confirm only
permitted/visible media references appear and private history is never exposed by permission alone.

**Acceptance Scenarios**:

1. **Given** community features (activity/projects/events/recommendations/statistics/challenges), **When**
   they reference media, **Then** references respect the acting user's visibility and viewers' permissions.
2. **Given** a user with Private media history, **When** community surfaces render, **Then** their media
   activity is not surfaced beyond the allowed audience (Privacy 021, Community 012).

### User Story 10 - Media availability vs service health vs sync (degraded modes) (Priority: P1)

The portal clearly distinguishes "media unavailable", "service unavailable", "sync in error", and "stale
data", and never turns a temporary service outage into removing the media from the catalog; the catalog
stays browsable with last-known data.

**Why this priority**: This encodes locked data-integrity rules at the Media/Connectors/Services boundary;
mishandling destroys catalog trust or user data.

**Independent Test**: Make a source unavailable, then a sync fail, then data go stale; confirm the catalog
remains browsable with last-known data, each condition is distinguishable, and the media is NOT removed
due to a temporary outage.

**Acceptance Scenarios**:

1. **Given** a temporary source outage, **When** it occurs, **Then** affected media show "service
   unavailable"/"stale" states but are NOT removed from the catalog.
2. **Given** distinct conditions, **When** shown, **Then** media-unavailable, service-unavailable,
   sync-error, stale, partial, temporarily-not-found, and data-conflict are distinguishable (per 006).
3. **Given** any degraded source, **When** the catalog is browsed, **Then** it remains consultable with the
   last-known data and unrelated media are unaffected.

### User Story 11 - Media extensibility (connectors, types, plugins, widgets, stats, actions, blocks, events) (Priority: P2)

Media is extensible by new connectors, new media types, plugins, widgets, statistics, actions, page
blocks, and events — all via the existing Extensibility (023) and the engines above, with the Core never
built around one provider.

**Why this priority**: Extensibility is the architectural guarantee that Media grows without a rewrite.

**Independent Test**: Add (a) a new connector providing a media capability, (b) a new media type, (c) a
plugin contributing a media widget / page block / action / statistic / event; confirm each integrates via
the defined extension points without changing the Core.

**Acceptance Scenarios**:

1. **Given** a new connector/type/plugin, **When** added, **Then** it integrates via capabilities (005) and
   extension points (023) without redesigning the Core Media.
2. **Given** a plugin media widget/block/action/statistic, **When** added, **Then** it integrates via the
   Dashboard (009)/detail-page extension points/Statistics (017) within permissions and the Design System.
3. **Given** a plugin-produced media event, **When** emitted, **Then** it enters the shared backbone (007)
   with proper shape/version.

### Edge Cases

- **Same content from multiple sources**: merged into one Media Object with provenance; conflicting
  metadata resolved by configured source-of-truth rules or provenance preserved (005) — never silent
  overwrite.
- **Source disconnected**: media representation/history retained (not auto-erased); shown as historical/
  stale; live actions for that source disabled (005/021).
- **Temporary outage ≠ deletion**: a service outage never removes media from the catalog.
- **Duplicate/late playback events**: idempotent per `occurred_at` (007) — no double XP/stat/notification.
- **Abandoned vs finished**: distinguished in history; thresholds for "finished" are policy (see OQ-116).
- **Resume across sources**: resume points are per media/user; if two sources report conflicting progress,
  reconcile per rules/provenance (see OQ-117).
- **Private history**: never public by default; "concerned users" and community references respect
  visibility (021).
- **Request quota vs priority**: quota purchasable with Coins; paid processing priority never exists (015).
- **Unknown/evolving media type**: handled via extensible type model; unknown attributes degrade gracefully.
- **Metadata/image missing**: shows a clear placeholder/partial state, not a broken entry.
- **AI media query exceeding permissions**: refused/omitted exactly as the user would be denied (018).
- **Campaign media conditions**: genre/type/title matching for campaigns uses media attributes via
  capabilities; deterministic matching (014/OQ-68).

## Requirements *(mandatory)*

### Functional Requirements

#### Unified Catalog & Content Identity
- **FR-001**: Media MUST provide a unified catalog spanning films, series, episodes, books/reading (where
  applicable), games (where applicable), and extensible additional types.
- **FR-002**: Each content item MUST have a **service-independent Media Object identity**; the same content
  from multiple sources MUST be a single Media Object with its sources listed as provenance (no
  duplicates).
- **FR-003**: A Media Object MUST expose metadata, posters/images, genres, tags, people, dates, durations,
  status, availability, and provenance/source.
- **FR-004**: New media types MUST be addable via extension without redesigning the Core Media model.
- **FR-005**: Content identity MUST be independent of source services; a source disappearing MUST NOT
  change a content item's identity.

#### Source Aggregation (via capabilities; no mandatory provider)
- **FR-006**: Media MUST aggregate source services (e.g., Plex, Radarr, Sonarr, Seerr, Grimmory, RomM,
  future connectors) **through capabilities** (Connectors 005), never by hard-coded service identity.
- **FR-007**: The Core Media MUST NOT depend on any single provider; no source service MUST be assumed
  mandatory.
- **FR-008**: When multiple sources provide the same capability/content, Media MUST merge per
  source-of-truth/provenance rules (005) and MUST NOT silently overwrite conflicting data.

#### Media Detail Page (extensible)
- **FR-009**: The detail page MUST present principal info, availability, sources, history, progression,
  permitted concerned users, relevant statistics, associated events, optional recommendations, available
  actions, external-service links, and plugin-contributed blocks.
- **FR-010**: Each detail-page section MUST render its own functional state so a slow/unavailable source
  does not block the rest (degraded mode per 006).
- **FR-011**: Detail-page content MUST be permission/privacy bounded (021); "concerned users" and personal
  activity MUST respect visibility and MUST NOT be public by default.
- **FR-012**: The detail page MUST expose defined extension points for plugin blocks (023), using the
  Design System and the standardized functional-state presentation (022).

#### Playback / Current Activity (source-agnostic)
- **FR-013**: Media MUST represent a Playback Session independently of the source service, with: media,
  user, source, progression, duration, device (if available), session start, session end, and state
  (playing/paused/finished/abandoned).
- **FR-014**: Current playback MUST be representable across multiple sources uniformly, with the Core not
  depending on any specific service.
- **FR-015**: Session lifecycle MUST emit media domain events (`media.playback_started`, progression
  updates, `media.playback_finished`, abandoned) with real `occurred_at` distinct from `received_at`.
- **FR-016**: If a source becomes unavailable mid-session, the session MUST show a degraded/stale state
  rather than disappearing or being incorrectly marked finished.

#### Media History
- **FR-017**: Media history MUST record play/read/game sessions, finished viewing, progression, resume
  points, abandoned plays, repeated plays, consultation history, provenance, and real timestamps
  (`occurred_at`).
- **FR-018**: Media history MUST feed Statistics, XP, Contribution, Achievements, Campaigns, Community
  activity, and Notifications **only via the event backbone (007)** and the reward engine (013) — no
  parallel reward or statistics logic.
- **FR-019**: Media event consumers MUST be idempotent per 007's dedup rule (no double rewards/stats on
  duplicate/late delivery).
- **FR-020**: Personal media history MUST NOT be public by default and MUST follow the privacy/retention/
  deletion lifecycle (021), including anonymization at final account deletion.

#### Requests
- **FR-021**: Media MUST represent requests from request-capability sources: request, requester, requested
  media, state, progression, availability, and history.
- **FR-022**: Request state changes at the source MUST reconcile per source-of-truth rules (005) and MAY
  trigger notifications (010) per preferences.
- **FR-023**: Additional request quota MAY be purchasable with Coins (via Marketplace 015 / ledger 013);
  paid request-processing **priority MUST NOT exist** or be offered.

#### Statistics (via Statistics 017)
- **FR-024**: Media MUST provide the data needed for media statistics (time watched/read/played, session
  counts, finished media, progression, genres, periods, users, services, trends) consumed by the
  Statistics engine (017); Media MUST NOT create a separate statistics system.
- **FR-025**: Media statistics MUST respect permissions/privacy and the "statistics are admin/portal-
  defined" rule (017) — users consume, not author.

#### Search & Discovery (via Search 008)
- **FR-026**: The catalog MUST be integrable with global Search (008), exposing media filters (type, genre,
  availability, source, user where permitted) and sort/categories, permission/privacy bounded.
- **FR-027**: Media MUST provide Discovery surfaces: new/recently-added, recently-watched, continue-
  watching (from resume points), recommendations, popular, related, and event-linked content — without
  imposing a specific recommendation algorithm.
- **FR-028**: Discovery and search results MUST be permission/privacy bounded and MUST show no dead-end
  empty states (a relevant next action is offered).

#### Gamification, Campaigns, Community, AI, Events, Notifications (integration)
- **FR-029**: Media events MUST be able to feed XP/Coins/Contribution/Achievements/Quests/Campaigns/
  Leaderboards/Community activity **only through the existing reward engine and anti-abuse rules** (013/
  012/014) — Media never grants rewards directly.
- **FR-030**: Campaigns (014) MUST be able to use media properties (genre, type, title, period, activity,
  service) as conditions; Media MUST only produce the attributes/events; the Campaigns/Events engine
  remains transversal.
- **FR-031**: The AI (018) MUST be able to use the media data the user may access (catalog, history,
  progression, availability, requests, statistics) strictly within the user's permissions, distinguishing
  real data from interpretation.
- **FR-032**: Media MUST produce events enabling notifications (010): media available, request updated,
  playback finished, resume available, playback error, and similar — delivered only via the notification
  engine, respecting preferences/permissions.

#### Availability, Services & Health (degraded modes)
- **FR-033**: Media MUST distinguish "media unavailable", "service unavailable", "sync in error", "stale",
  "partial", "temporarily not found", and "data conflict" (aligned with Services & Health 006).
- **FR-034**: A temporary source outage or sync error MUST NOT remove a media item from the catalog; the
  catalog MUST remain consultable with last-known data.
- **FR-035**: Media availability MUST compose with service health and sync state as distinct facts (never
  conflated), consistent with 006.

#### Extensibility
- **FR-036**: Media MUST be extensible by new connectors, media types, plugins, widgets, statistics,
  actions, page blocks, and events via the existing Extensibility (023) and the engines above, with the
  Core never built around one provider.

#### Permissions & Privacy (visibility levels)
- **FR-037**: Media data MUST support the standard visibility levels (Public, Community, Leaderboards only,
  Private) per Privacy (021); personal viewing/reading history MUST default to not-public.
- **FR-038**: All Media surfaces/actions MUST be gated server-side by the authorization engine (003,
  deny-by-default) and MUST respect privacy; permission MUST NOT override privacy.
- **FR-039**: Media actions MUST be permission-gated and audited where sensitive (e.g., destructive source
  actions, admin catalog operations), consistent with 003/006.

#### Events & Object Integrity
- **FR-040**: Media domain events MUST follow the Event Model shape (id, type, `occurred_at`,
  `received_at`, source, actor/context, object/reference, metadata, version) per 007.
- **FR-041**: Media MUST NOT expose secrets from source services; external-service links MUST respect
  permissions and MUST NOT leak credentials.

### Object Model (functional, not implementation)

- **Media Object**: service-independent content identity (type, metadata, images, genres, tags, people,
  dates, durations, status, availability). 1 Media Object ↔ many **Source Bindings**.
- **Source Binding**: links a Media Object to a Source (via a capability) with provenance, source-specific
  ids, availability, and last-sync info. Disconnecting a source removes the live binding, not the Media
  Object or its history.
- **Media Type**: extensible classification (film/series/episode/book/game/…); series → seasons → episodes
  relationships where applicable.
- **Playback Session**: (media, user, source, state, progression, duration, device?, started_at, ended_at).
- **Media History Entry**: a historized fact about a user+media (finished/abandoned/resumed/repeated/
  consulted) with provenance and `occurred_at`.
- **Resume Point**: per user+media progress enabling "continue watching".
- **Media Request**: (requested media, requester, state, progression, availability, history) from a
  request-capability source.
- **Availability**: derived view combining source bindings + service health + sync state (distinct facts).

**Relationships**: Media Object → Source Bindings / sessions / history / statistics / events / requests /
achievements. Series → Episodes. User → sessions / history / resume points / requests (permission/privacy
bounded).

### Media Domain Events (produced by Media; consumed via 007)

- `media.added`, `media.updated`, `media.removed` (catalog)
- `media.availability_changed`
- `media.playback_started`, `media.playback_progressed`, `media.playback_paused`,
  `media.playback_finished`, `media.playback_abandoned`, `media.playback_error`
- `media.resume_available`
- `media.request_created`, `media.request_updated`, `media.request_available`
- (All consumed by Statistics/Gamification/Campaigns/Community/Notifications/AI/Automations via the
  backbone; Media only produces.)

### Key Entities

- **Media Object / Source Binding / Media Type** — unified identity + provenance + extensible types.
- **Playback Session / Resume Point / Media History Entry** — source-agnostic activity + memory.
- **Media Request** — representation of a request-service item.
- **Availability** — composed from bindings + service health + sync state (006).
- **Capability (referenced)** — the contract through which sources provide media data (005).
- **Statistic / Reward / Campaign / Notification / Permission / Visibility (referenced)** — owned by their
  engines (017/013/014/010/003/021); Media feeds/consumes them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Identical content from multiple sources appears as more than one catalog entry in 0% of
  cases (single Media Object with provenance in 100%).
- **SC-002**: Media references a concrete source by hard-coded identity (instead of a capability) in 0% of
  cases; Core Media functions with a given provider absent in 100% of applicable cases.
- **SC-003**: A temporary source outage/sync error removes a media item from the catalog in 0% of cases;
  the catalog stays browsable with last-known data in 100% of such cases.
- **SC-004**: Current playback is representable uniformly across sources in 100% of supported sources,
  with no Core dependency on a single service.
- **SC-005**: Duplicate/late media events cause double XP/stats/notifications in 0% of cases (idempotent
  via 007).
- **SC-006**: Media rewards are granted outside the reward engine/anti-abuse in 0% of cases (always via
  013).
- **SC-007**: Personal media history is public by default in 0% of cases; private history is exposed by
  permission alone in 0% of cases (021).
- **SC-008**: A paid request-processing priority exists/offered in 0% of cases; quota purchases increase
  quota in 100% of valid cases.
- **SC-009**: media-unavailable, service-unavailable, sync-error, and stale are distinguishable in 100% of
  applicable surfaces (006).
- **SC-010**: AI media answers expose data beyond the user's permissions in 0% of cases; 100% of media
  statistics come from the Statistics engine (no separate system).
- **SC-011**: A new connector/media-type/plugin integrates without Core redesign in 100% of defined cases.
- **SC-012**: Each major Media feature (catalog, detail, playback, history, requests, search/discovery) has
  verifiable acceptance criteria in 100% of cases (this spec).

## Assumptions

- Source aggregation, sync, disconnection-not-delete, and conflict handling are owned by Connectors (005);
  Media consumes capabilities and composes provenance.
- The availability-vs-health-vs-sync distinctions are owned by Services & Health (006); Media reuses them.
- The event/history backbone and dedup rule are owned by Events & History (007); Media only produces media
  events and consumes idempotently.
- Statistics definitions/engine (017), the reward engine/anti-abuse/ledger (013), campaign modifiers (014),
  notification delivery (010), AI (018), Privacy (021), Search (008), Dashboard widgets (009), and
  Extensibility (023) are owned by their specs; Media integrates, never re-implements.
- "Finished" thresholds, resume reconciliation, and recommendation sourcing are product/plan decisions
  (flagged below), not invented here.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation. (These are genuinely Media-specific; cross-cutting ones already tracked in
other specs are referenced, not re-opened.)

- **OQ-115 (Identity resolution/matching)**: Confirm how the portal decides two source items are the "same
  content" (external ids, metadata matching, manual merge) and how mismatches/merges are handled —
  critical for FR-002.
- **OQ-116 ("Finished" thresholds)**: Confirm per-type completion thresholds (e.g., % watched/read/played)
  distinguishing finished vs abandoned, feeding rewards/stats.
- **OQ-117 (Cross-source progress reconciliation)**: Confirm how conflicting progress/resume points from
  multiple sources reconcile (latest `occurred_at` wins, per-source, or unified), consistent with 005
  source-of-truth.
- **OQ-118 (Recommendations ownership)**: Confirm whether recommendations are powered by Statistics (017),
  AI (018), or a dedicated mechanism — the spec requires the surface, not the algorithm.
- **OQ-119 (Media-object provenance authority)**: Confirm which source is authoritative for which metadata
  field when sources disagree (per-field source-of-truth), aligning with Connectors OQ-23/Privacy OQ-103.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with (does not re-implement): `005-connectors` (capabilities/sync/provenance/disconnection),
  `006-services-health` (availability vs health vs sync; degraded states), `007-events-history` (media
  events, idempotency, history), `008-search-command-palette` (media search), `009-dashboard-widgets`
  (current playback / continue-watching widgets), `010-notifications` (media notifications),
  `012-community` (media references within privacy), `013-gamification-economy` (rewards/anti-abuse/ledger),
  `014-campaigns` (media-property conditions), `015-marketplace` (request quota, no paid priority),
  `017-statistics` (media statistics), `018-ai-capability` (AI media queries within permissions),
  `019-automations` (media triggers), `021-privacy-data-lifecycle` (visibility, personal-history-not-public,
  deletion/anonymization), `023-extensibility` (connectors/types/plugins/widgets/blocks/actions/events).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `product/GLOSSARY.md`, `architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`,
  `architecture/DATA_MODEL.md`, `features/FEATURE_CATALOG.md` (MEDIA-001→006, HOME-003/005/006).
- Contradictions check: none found with existing specs (see Audit §; this spec closes the Media coverage
  gap H1). Media produces the `media.*` events the backbone and consumers already referenced.
