# Contracts — Events & History

## Publisher (real implementation of the kernel `EventPublisher` port)
`publish(event_type, payload, *, occurred_at, source_system, source_event_id=None, actor=None, subject=None, correlation_id=None, uow)` → `event_id | Duplicate(event_id)`; validates against the type registry, derives the dedup key, writes event + dedup key in the caller's transaction. Idempotent: duplicate ⇒ same logical result, no second event.

## Registry
`register_event_type(EventType(...))` at import time; unknown types rejected at publish (dev) / quarantined (ingest).

## Consumers
`@consumer(name, types=[...], replay_safe=False)` handler `(event, ctx)`; `ctx.idempotent_effect(key)` returns False when already applied; `ctx.replay` / `ctx.as_of` for replay.

## History query (capability `events.history`)
`for_user(user_id, filters, cursor)` · `for_subject(type, id, filters, cursor)` · results pass through `VisibilityFilter` + `require()`; personal history default owner-only.

## Replay
`ReplayService.rebuild(projection, from, to)`: deterministic, ordered, never re-emits external effects.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/me/history` | `users.self.manage` |
| GET `/subjects/{type}/{id}/history` | per-domain read permission + visibility |
| GET `/admin/events`, `/admin/events/deliveries`, `/admin/events/quarantine` | `events.manage` (privacy-bounded payload view) |
| POST `/admin/events/quarantine/{id}/release|discard` | `events.manage` (sensitive, audited) |
| POST `/admin/replay` | `events.replay` (sensitive, audited, confirmation) |
Problem codes: `events.unknown_type`, `events.invalid_payload`, `events.duplicate` (informational).
