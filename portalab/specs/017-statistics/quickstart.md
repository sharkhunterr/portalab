# Quickstart — Statistics
1. Admin activates a definition (e.g. `users.active_by_day`); emit sample `user.signed_in` events → buckets fill; the chart renders for authorized users; a user cannot create their own chart.
2. Switch period `month` → `last_n_days`; same values via dashboard widget and via the API (consistency).
3. Define a statistic locked at level 5 (stub progression) → below level: `locked` with hint, no data computed; at level 5 → available.
4. Community statistic with fewer than 5 contributors → `insufficient_data`; add contributors → value appears.
5. Stop a contributing service → statistic shows `partial`/`stale` with `as_of`; others unaffected.
6. Replay events with a duplicated event id → totals unchanged.
7. Generate Wrapped for a user → immutable snapshot; delivery respects notification preferences (or in-app only if 010 absent).
