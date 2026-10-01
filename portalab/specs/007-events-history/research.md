# Research — Events & History (spec 007, roadmap step 5)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **One append-only event store = the history** (`events.events`, monthly partitions); no separate "history" copy. History views are queries filtered by permission/privacy | Single event model (CD-012), no duplicated truth | Event store + separate history table |
| R2 | **Producer writes the event inside its own transaction** (outbox semantics: state change and event commit atomically); a dispatcher fans out afterwards | Atomic publish, no dual write | Publish after commit (lost events) |
| R3 | **Dedup via a dedicated `events.dedup_keys` table** (unique (type, dedup_key)) because partitioned tables cannot hold a global unique index; key = reliable source id, else deterministic composite of declared fields, never a timestamp alone | CD-012, spec FR-012; works with partitioning | Unique index on partitions |
| R4 | **Per-type registry** (`EventType`: name, version, Pydantic payload schema, `dedup_fields`, `source_id_reliable`, retention class, visibility class); unknown/invalid events go to `events.quarantine` | FR-001..004, FR-014 | Free-form payloads |
| R5 | **Consumers have independent cursors and delivery records** (`consumer_offsets`, `deliveries`); at-least-once; handlers idempotent through `idempotent_effect(consumer, key)`; poison events become dead letters after N attempts | Failure isolation (FR-007), idempotent effects (FR-011) | Shared queue (one slow consumer blocks others) |
| R6 | **Replay is explicit and side-effect-safe**: `ReplayService` feeds a projection events in order with `replay=True` and `as_of=occurred_at`; handlers declare `replay_safe`; original events untouched | FR-027..030 | Re-publishing old events |
| R7 | **Payloads carry ids/facts, never PII bodies or secrets** (extends 021's append-only rule); a validator rejects fields classified as PII/secret | Privacy, retention by partition drop | PII in payloads + scrub |
| R8 | **Audit stays in `audit.audit_entries`** (003/021); 007 adds `event_id` correlation and shares partition tooling; sensitive actions emit both an event and an audit entry | CD-013, FR-023/024 | Folding audit into events |
| R9 | **Ordering**: global insert `seq` for consumer ordering + `occurred_at` for attribution; consumers needing causal order per object use per-object `object_seq` | FR-013 | Relying on timestamps |
| R10 | **Live delivery** to browsers through the SSE endpoint as one more subscriber (permission-filtered) | 001 US4 | Separate broker |

No `NEEDS CLARIFICATION` remains. OQ-30..34 use registry defaults (dedup by registered fields; at-least-once + idempotent; admin-triggered replay; retention via config; events not public by default).
