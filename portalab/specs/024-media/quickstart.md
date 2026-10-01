# Quickstart — Media
1. With two fake services both providing `media.library`, sync the same film (shared `tmdb` id) → one Media Object with two sources; per-field values follow the configured priority; admin override beats both.
2. Remove the film from one service → object stays, `availability` reflects the remaining source; remove from both → object stays `unavailable`; service outage alone changes nothing in the catalog.
3. Link a user to a service account; emulate playback → `PlaybackSession` appears uniformly; pausing/resuming emits throttled `media.playback_paused|progressed` events; kill the service → session `stale` then `interrupted` (`media.playback_error`).
4. Reach 90 % of a movie → `media.playback_finished` once (replay-safe); resume point follows the latest `occurred_at` across two sources.
5. Submit a request through the request service (within quota) → mirrored state; exceed quota → problem `media.request_quota_exceeded`.
6. Open the detail page with one source down → only that section shows `unavailable`; another user's private history is absent; a plugin block appears from its slot.
