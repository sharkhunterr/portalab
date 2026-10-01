# Quickstart — Events & History
1. Publish the same registered event twice (same source id) → one stored event, second call returns `Duplicate`.
2. Register two consumers; make one fail → the other advances; the failing one retries then dead-letters, visible in `/admin/events/deliveries`.
3. Publish an event with an unknown type → quarantined, not stored in `events.events`.
4. Rebuild a projection with `ReplayService` → same result, no notifications re-sent, originals unchanged.
5. `GET /me/history` as the owner works; as another permitted user returns nothing private.
