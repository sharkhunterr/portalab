# Feature Specification: Events & History

**Feature Branch**: `007-events-history`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Events & History system — a cross-cutting portal mechanism."

## Role of This Document

This is a **detailed feature specification** for Events & History — the transversal backbone that
records what happens anywhere in the portal and lets any feature react without knowing the origin.
It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`) and composes with Roles & Permissions
(`specs/003-roles-permissions/spec.md`), Portal Core shell (`specs/004-portal-core-shell/spec.md`),
Connectors (`specs/005-connectors/spec.md`), and Services & Health
(`specs/006-services-health/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws primarily on `architecture/EVENT_MODEL.md`,
`architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/DATA_MODEL.md`, and
`product/BUSINESS_RULES.md`.

Scope boundary: this spec owns the **event and history mechanism** itself — the shape of a domain
event, ingestion of incoming events, publication to consumers, idempotency/deduplication, the
history store (provenance, context, retention, visibility), audit's relationship to events, and
historical reconstruction/replay. It does **not** own the business meaning of specific consumers
(Statistics, Gamification/XP/Coins, Achievements, Community, Notifications, Dashboard, AI) — those
are defined by their own specs and merely illustrate consumption here. It does not own connector
sync internals (owned by Connectors) nor the authorization engine. It chooses no technology and
contains no implementation detail.

**Terminology** (aligned with the Event Model and global spec, OQ-1): **Domain Event** = a recorded
fact that something happened; **Campaign** = a themed time-bound operation (not an event).
`occurred_at` = real occurrence time; `received_at` = portal receipt time.

### Canonical Example (reference flow)

A single real-world action fans out to many independent consumers without any consumer knowing the
origin service:

```
Plex (service) --> playback.finished (Domain Event, occurred_at = real time)
        --> History (persisted with provenance + context)
        --> Statistics        (updates watch stats)
        --> XP                 (grants progression)
        --> Coins              (grants internal currency per rules)
        --> Achievement        (may unlock a milestone)
        --> Community Activity  (may surface activity within visibility)
        --> Notification        (per user preferences)
        --> Dashboard           (Since Last Login / widgets reflect it)
        --> AI                  (may reference it within the user's permissions)
```

Each consumer reacts to the **event type and payload/capability**, never to "Plex" specifically.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One action fans out to many consumers without origin coupling (Priority: P1)

A single action (e.g., finishing a media item) produces one domain event that many independent
features consume (history, statistics, XP, coins, achievements, community, notification, dashboard,
AI) — each reacting to the event type and payload, none depending on the originating service.

**Why this priority**: Producer/consumer decoupling via events is the transversal backbone that makes
the whole product loop work; without it every feature would couple to every service.

**Independent Test**: Emit one representative event; confirm each interested consumer reacts
independently, that disabling or failing one consumer does not affect the others, and that no
consumer references the origin service by name.

**Acceptance Scenarios**:

1. **Given** a recordable action, **When** it occurs, **Then** exactly one domain event is recorded and
   all interested consumers are able to react to it.
2. **Given** multiple consumers of the same event, **When** it is published, **Then** each reacts
   independently and the failure of one consumer does not prevent the others from reacting.
3. **Given** a consumer, **When** it reacts, **Then** it depends only on the event type and payload/
   capability, never on the identity of the originating service.
4. **Given** a new consumer is added later, **When** the same event type occurs, **Then** the new
   consumer can react without changes to producers or existing consumers.

### User Story 2 - Correct event shape: origin, real timestamp, actor, service, content, context (Priority: P1)

Every domain event carries a consistent, self-describing shape — identifier, type, origin/source,
real occurrence time, actor/user, service reference where applicable, content/object reference,
context/metadata, and version — so consumers and history have everything they need.

**Why this priority**: A consistent, versioned event shape is what makes decoupled consumption and
faithful history possible; missing fields break downstream features.

**Independent Test**: Inspect a recorded event and confirm it includes id, type, source,
`occurred_at`, `received_at`, actor/context, object/reference, metadata, and version.

**Acceptance Scenarios**:

1. **Given** any domain event, **When** it is recorded, **Then** it contains at least: event id, type,
   source/origin, `occurred_at`, `received_at`, actor/context, object/reference, metadata, version.
2. **Given** an event, **When** `occurred_at` and `received_at` differ, **Then** both are preserved and
   `occurred_at` represents the real occurrence time.
3. **Given** an event type that evolves, **When** a new version is introduced, **Then** the version is
   recorded and older events keep their original version/meaning.

### User Story 3 - Incoming events, idempotency, and deduplication (Priority: P1)

Events arriving from external sources or internal producers — possibly duplicated, late, or
out-of-order — are ingested so that duplicate delivery produces the same result as single delivery,
and ordering/attribution uses the real occurrence time.

**Why this priority**: Idempotency and deduplication are locked requirements; without them, a single
playback could grant XP/coins twice or corrupt statistics.

**Independent Test**: Deliver the same event twice (and out of order); confirm consumers and history
reflect it once, attributed by `occurred_at`, with no double-counting.

**Acceptance Scenarios**:

1. **Given** an event delivered more than once, **When** ingested, **Then** it is deduplicated and the
   outcome is identical to a single delivery (idempotent consumers).
2. **Given** events arriving out of order, **When** processed, **Then** attribution/ordering uses
   `occurred_at`, not `received_at`.
3. **Given** a late-arriving event, **When** ingested, **Then** it is recorded with its real
   `occurred_at` and reconciled without corrupting prior history.
4. **Given** a duplicate that was already consumed, **When** redelivered, **Then** no consumer applies
   its effect a second time (e.g., no duplicate reward).

### User Story 4 - Outgoing events and multi-feature consumption (Priority: P2)

Producers publish events without knowing who consumes them; consumers subscribe to event types; the
same event is consumed by many features in parallel, and a slow/failing consumer does not block
producers or other consumers.

**Why this priority**: The publish/subscribe separation and non-blocking fan-out are what keep the
portal resilient and extensible.

**Independent Test**: Publish an event with several subscribers, one of them slow/failing; confirm the
producer is unaffected, fast consumers proceed, and the failing one can recover and process later
without duplicate effects.

**Acceptance Scenarios**:

1. **Given** a producer publishes an event, **When** it is published, **Then** the producer does not
   need to know or wait for consumers.
2. **Given** a slow or failing consumer, **When** an event is published, **Then** other consumers and
   the producer are unaffected (failure isolation).
3. **Given** a consumer recovers after a failure, **When** it processes pending events, **Then** it
   does so idempotently with no duplicated effects.

### User Story 5 - History with provenance, context, and visibility (Priority: P1)

Events are persisted as history with their provenance and context; history is queryable by permitted
features and users, but historized does not mean public — visibility and permissions gate who sees
what.

**Why this priority**: History is the memory of the portal and feeds statistics, dashboards, and AI;
the "historized ≠ public" rule is locked and privacy-critical.

**Independent Test**: Record events, then view history as users with different permissions/visibility;
confirm provenance/context are retained and that private/historized data is not exposed beyond what
permissions and privacy allow.

**Acceptance Scenarios**:

1. **Given** a recorded event, **When** stored in history, **Then** its provenance (origin, actor,
   service where applicable) and context are retained.
2. **Given** history, **When** queried, **Then** results are gated by the viewer's permissions and by
   privacy/visibility; historized data is not public by default.
3. **Given** a user's own history vs another user's, **When** viewed, **Then** access respects
   `users.self` scope, permissions, and privacy preferences.

### User Story 6 - Retention and privacy-aware lifecycle (Priority: P2)

History is retained according to policy; personal/identifying history follows the privacy and deletion
rules (anonymized/removed at final account deletion), while aggregate/integrity-necessary history may
be preserved.

**Why this priority**: Retention ties the event backbone to privacy and deletion rules; mishandling it
would either lose integrity data or retain personal data improperly.

**Independent Test**: Apply retention policy and an account deletion; confirm personal history is
anonymized/removed while integrity-necessary/aggregate history persists and transaction integrity is
preserved.

**Acceptance Scenarios**:

1. **Given** a retention policy, **When** it applies, **Then** history beyond the policy is handled per
   policy without breaking integrity-necessary records.
2. **Given** final account deletion, **When** it runs, **Then** personal/identifying history is
   anonymized or removed while aggregate/integrity history may remain (not identifying).
3. **Given** anonymized history, **When** retained, **Then** it is not re-identifiable and was not made
   public as a side effect.

### User Story 7 - Audit relationship to events (Priority: P2)

Sensitive actions produce audit entries; audit is related to but distinct from general history — audit
is an append-only, tamper-evident record of who did what, while history is the broader record of what
happened.

**Why this priority**: Clear separation of audit and history keeps accountability trustworthy and
prevents conflating "something happened" with "someone sensitive-acted".

**Independent Test**: Perform a sensitive action and a normal action; confirm the sensitive one yields
an audit entry (actor/action/time/context/result) and that audit is append-only and not merged into
general history.

**Acceptance Scenarios**:

1. **Given** a sensitive action, **When** it occurs, **Then** an audit entry is recorded with actor,
   action, timestamp, context, decision/result.
2. **Given** audit entries, **When** stored, **Then** they are append-only and not rewritten.
3. **Given** audit vs general history, **When** compared, **Then** they are distinct records serving
   distinct purposes (accountability vs memory).

### User Story 8 - Historical reconstruction / replay (Priority: P2)

Authorized reconstruction can rebuild a derived view (e.g., a statistic or a consumer's projection)
from the historized events, deterministically and without altering the original events or
double-applying irreversible effects.

**Why this priority**: Reconstruction is how the portal repairs a derived view or onboards a new
consumer; it must be deterministic and must respect historical rule versions.

**Independent Test**: Rebuild a derived projection from history; confirm the result is deterministic,
matches the recorded events, respects the rule version in force at each event's time, and does not
re-trigger one-off side effects (e.g., re-sending notifications or re-granting rewards).

**Acceptance Scenarios**:

1. **Given** historized events, **When** a projection is reconstructed, **Then** the result is
   deterministic and consistent with the events.
2. **Given** reconstruction, **When** it runs, **Then** it applies the rule/version in force at each
   event's `occurred_at` (historical rules are not rewritten).
3. **Given** reconstruction, **When** it runs, **Then** it rebuilds derived state without re-emitting
   one-off external side effects (no duplicate notifications/rewards).
4. **Given** original events, **When** reconstruction runs, **Then** the original events are not
   modified.

### Edge Cases

- **Duplicate delivery**: The same event delivered multiple times is recorded and consumed once;
  no consumer applies effects twice (no duplicate XP/coins/notifications).
- **Out-of-order / late arrival**: Ordering and attribution use `occurred_at`; a late event is placed
  correctly in history and reconciled without corrupting prior derived state.
- **Clock skew between source and portal**: `occurred_at` is the source's real time; `received_at`
  records portal receipt; both are retained so skew is visible rather than hidden.
- **Consumer failure mid-fan-out**: The failing consumer does not block others or the producer; on
  recovery it processes idempotently.
- **Unknown/malformed incoming event**: Rejected or quarantined with an actionable error; it does not
  corrupt history or crash consumers.
- **Event version mismatch**: A consumer encountering an unknown version handles it safely (ignores or
  adapts) without breaking; historical events keep their original version.
- **Origin service later disconnected**: Historized events from it remain (not auto-erased), consistent
  with the Connectors rule; new live events simply stop.
- **Private data in events**: Event payload/history respects visibility; historized ≠ public; sensitive
  content is not exposed beyond permissions/privacy, and secrets are never stored in events.
- **Reconstruction with one-off side effects**: Replay rebuilds derived state only; it must not
  re-send notifications, re-grant rewards, or re-call external services.
- **Retention vs integrity**: Retention cleanup never deletes integrity-necessary records (e.g.,
  economy transactions) required by other rules.
- **High-volume fan-out**: A burst of events does not cause one slow consumer to block the ingestion or
  other consumers.
- **Deduplication key ambiguity**: When a source does not provide a reliable unique id, the system uses
  a defined deduplication strategy rather than silently double-counting (see OQ-30).

## Requirements *(mandatory)*

### Functional Requirements

#### Event Shape & Semantics
- **FR-001**: Every domain event MUST carry at least: event id, type, source/origin, `occurred_at`
  (real occurrence time), `received_at` (portal receipt time), actor/context, object/reference,
  metadata, and version.
- **FR-002**: `occurred_at` MUST represent the real occurrence time and MUST NOT be overwritten by the
  receipt time; both MUST be retained.
- **FR-003**: Event types MUST be versioned; introducing a new version MUST NOT change the meaning or
  version of previously recorded events.
- **FR-004**: An event MUST be self-describing enough that a consumer can react using only the event
  type and payload/capability, without knowing the originating service.

#### Producers, Consumers & Decoupling
- **FR-005**: Producers MUST be able to publish events without knowing which consumers exist.
- **FR-006**: Multiple consumers MUST be able to react to the same event independently and in parallel.
- **FR-007**: A slow or failing consumer MUST NOT block the producer or other consumers (failure
  isolation).
- **FR-008**: Adding a new consumer MUST NOT require changes to producers or existing consumers.
- **FR-009**: Consumers MUST NOT depend on the identity of the originating service to react.

#### Ingestion, Idempotency & Deduplication
- **FR-010**: The system MUST ingest incoming events from internal producers and external sources
  (e.g., via connectors) into the same event mechanism.
- **FR-011**: Event consumers MUST be idempotent wherever duplicate delivery is possible; duplicate
  delivery MUST produce the same result as single delivery.
- **FR-012**: The system MUST deduplicate events using a defined deduplication identity/strategy so a
  duplicate is not recorded or consumed twice.
- **FR-013**: Ordering and attribution MUST use `occurred_at`; out-of-order and late events MUST be
  reconciled without corrupting prior history or derived state.
- **FR-014**: Malformed or unknown incoming events MUST be rejected or quarantined with an actionable
  error, without corrupting history or breaking consumers.

#### History, Provenance & Context
- **FR-015**: The system MUST persist events as history, retaining provenance (origin, actor, service
  where applicable) and the context needed by consuming features.
- **FR-016**: History MUST be queryable by permitted features and users; historized data MUST NOT be
  public by default.
- **FR-017**: Access to history MUST be gated by the authorization engine (deny-by-default) and MUST
  respect privacy/visibility preferences and admin policies (permissions do not override privacy).
- **FR-018**: A disconnected origin service's historized events MUST remain available (not
  auto-erased), consistent with the Connectors rule.

#### Visibility
- **FR-019**: Event/history visibility MUST follow the same visibility levels used elsewhere (Public,
  Community, Leaderboard-only, Private) and MUST never auto-publish private/historized data.
- **FR-020**: Secrets MUST NEVER be stored in event payloads or history.

#### Retention & Privacy Lifecycle
- **FR-021**: History MUST be retained per configurable retention policy without deleting
  integrity-necessary records required by other rules (e.g., economy transactions).
- **FR-022**: At final account deletion, personal/identifying history MUST be anonymized or removed
  while aggregate/integrity history MAY be preserved in non-identifying form, and anonymized history
  MUST NOT be re-identifiable or made public.

#### Audit Relationship
- **FR-023**: Sensitive actions MUST produce audit entries containing actor, action, timestamp,
  context, and decision/result; audit MUST be append-only and not rewritten.
- **FR-024**: Audit MUST be a distinct record from general history (accountability vs memory) even
  though both may be derived from or accompany events.

#### Synchronization Relationship
- **FR-025**: Events ingested via synchronization MUST follow the same idempotency/dedup/`occurred_at`
  rules; sync receipt time MUST NOT be treated as occurrence time.
- **FR-026**: A full resync feeding events MUST NOT cause duplicate consumer effects and MUST NOT
  blindly destroy historized events (consistent with the Connectors resync rule).

#### Historical Reconstruction / Replay
- **FR-027**: The system MUST support authorized reconstruction of a derived view/projection from
  historized events, producing a deterministic result consistent with the events.
- **FR-028**: Reconstruction MUST apply the rule/version in force at each event's `occurred_at`;
  historical rules/transactions MUST NOT be rewritten.
- **FR-029**: Reconstruction MUST rebuild derived state only and MUST NOT re-emit one-off external side
  effects (no duplicate notifications, rewards, or external calls).
- **FR-030**: Reconstruction MUST NOT modify the original historized events.

#### Observability
- **FR-031**: The event/history mechanism MUST be observable (e.g., ingestion/consumption outcomes,
  dedup/quarantine counts) and MUST surface failures as actionable rather than silent.

### Event Lifecycle

**Stages**: Produced/Received → Validated → Deduplicated → Recorded (History) → Published to
Consumers → Consumed (idempotently) → Retained → (optionally) Replayed for reconstruction.

**Invariants**:
- One logical occurrence corresponds to one recorded event (after deduplication), regardless of how
  many times it was delivered.
- `occurred_at` is immutable and authoritative for ordering/attribution; `received_at` is recorded
  separately.
- Recorded events are immutable; derived/projected state may be rebuilt, the events themselves are
  not rewritten.
- Historized ≠ public; access is always gated by permissions and privacy.
- Consumption effects are idempotent; reconstruction never re-emits one-off side effects.

### Worked Example — `playback.finished`

1. A media service reports a finished playback; the portal ingests one `playback.finished` event with
   `occurred_at` = the real finish time, actor = the user, service = the media service, object = the
   media item, metadata = position/duration, version = N.
2. Deduplication ensures a redelivered report does not create a second event.
3. The event is recorded in History with provenance and context.
4. Independent consumers react: Statistics updates watch stats; XP grants progression; Coins grants
   currency per the current rules; Achievements may unlock; Community Activity may surface it within
   visibility; Notification is produced per the user's preferences; Dashboard reflects it (Since Last
   Login / widgets); AI may reference it within the user's permissions.
5. If one consumer (e.g., Notification) is down, the others still react; Notification processes on
   recovery without duplicate sends.
6. None of the consumers reference "the media service" by name — they react to `playback.finished`.

### Key Entities

- **Domain Event**: The recorded fact — id, type, source/origin, `occurred_at`, `received_at`,
  actor/context, object/reference, metadata, version.
- **Event Type (versioned)**: The classification of an event with an evolving, versioned contract.
- **Producer**: Any source (internal feature or connector/service) that publishes events.
- **Consumer/Subscriber**: Any feature that reacts to event types; reacts idempotently; origin-agnostic.
- **History Entry**: The persisted, immutable record of an event with provenance and context.
- **Deduplication Key/Record**: The identity/strategy used to recognize duplicates.
- **Projection / Derived View**: A consumer-maintained view rebuildable via reconstruction.
- **Retention Policy (referenced)**: Governs history lifecycle; composes with Privacy/deletion rules.
- **AuditEntry (referenced)**: Append-only accountability record for sensitive actions; distinct from
  history.
- **Visibility/Permission (referenced)**: Gates who may read which history (owned by Roles &
  Permissions / Privacy).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single real occurrence results in exactly one recorded event after deduplication in
  100% of cases, regardless of delivery count.
- **SC-002**: Duplicate delivery causes a duplicated consumer effect (e.g., double XP/coins/
  notification) in 0% of cases.
- **SC-003**: Ordering/attribution uses `occurred_at` in 100% of cases; `received_at` is used as
  occurrence time in 0% of cases.
- **SC-004**: A failing consumer blocks the producer or other consumers in 0% of cases; a recovered
  consumer reprocesses without duplicate effects in 100% of cases.
- **SC-005**: Consumers reference the originating service by identity in 0% of cases (100% react to
  type/payload).
- **SC-006**: Adding a new consumer requires changes to producers or existing consumers in 0% of cases.
- **SC-007**: History access exposes private/historized data beyond permissions/privacy in 0% of cases
  (historized ≠ public upheld in 100%).
- **SC-008**: At final account deletion, personal history is anonymized/removed in 100% of cases while
  integrity-necessary records are preserved in 100% of cases; anonymized history is re-identifiable in
  0% of cases.
- **SC-009**: Reconstruction of a projection is deterministic and consistent with history in 100% of
  runs, applies the historical rule version in 100% of cases, and re-emits one-off side effects in 0%
  of runs.
- **SC-010**: 100% of sensitive actions produce an append-only audit entry; audit entries are rewritten
  in 0% of cases.

## Assumptions

- Specific consumers (Statistics, XP, Coins, Achievements, Community, Notifications, Dashboard, AI) are
  owned by their own specs; they appear here only to illustrate decoupled consumption.
- The event type catalog is owned collectively by the producing domains; this spec fixes the event
  shape, lifecycle, and guarantees, not the exhaustive list of types.
- The deduplication identity is derived from a source-provided unique id when available, otherwise from
  a defined composite strategy; the exact strategy is policy. (Flagged as OQ-30.)
- Delivery semantics are effectively at-least-once with idempotent consumers (the safe default for the
  stated requirements); exactly-once is not assumed at the transport level. (Flagged as OQ-31.)
- Retention durations and granularity are configurable administrative policy consistent with Privacy.
- The authorization and privacy/visibility engines are owned by their specs; this spec consumes their
  decisions for history access.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-30 (Deduplication identity)**: Confirm the canonical deduplication key/strategy, especially for
  sources that do not provide a reliable unique id, and the deduplication time window.
- **OQ-31 (Delivery & ordering guarantees)**: Confirm the required delivery semantics (at-least-once +
  idempotent is assumed) and whether any ordering guarantees are required beyond `occurred_at`
  attribution.
- **OQ-32 (Reconstruction scope & triggers)**: Confirm who may trigger reconstruction/replay, for which
  projections, and whether it is on-demand (repair) only or also used to onboard new consumers over
  historical data.
- **OQ-33 (History retention defaults)**: Confirm whether product-level default retention windows must
  be fixed here or left entirely to admin policy, and how they interact with per-domain needs.
- **OQ-34 (Event visibility defaults)**: Confirm default visibility for newly recorded events/history
  (e.g., Private/owner-only by default) to guarantee historized-≠-public from creation.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (history access gating, audit),
  `specs/004-portal-core-shell/spec.md` (shell reacts to events for navigation/degraded state),
  `specs/005-connectors/spec.md` (incoming events via sync; `occurred_at`/idempotency alignment), and
  `specs/006-services-health/spec.md` (health-history points as events).
- Depends on / references: `architecture/EVENT_MODEL.md`, `architecture/FUNCTIONAL_ARCHITECTURE.md`,
  `architecture/DATA_MODEL.md`, `product/BUSINESS_RULES.md`.
- Related specs (not owned here): Statistics, Gamification (XP/Coins/Achievements/Quests/Campaigns),
  Community, Notifications, Dashboard, AI, Automations, Audit (if separated), and the Privacy spec (021) — all
  of which produce and/or consume events defined by this mechanism.
