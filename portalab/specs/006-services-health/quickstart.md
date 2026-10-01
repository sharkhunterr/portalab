# Quickstart — Services & Health
1. With the `fake` connector enabled, probes run → `service_state` becomes Operational; stop the fake service → Unavailable after the threshold; recover → Operational (events emitted once each).
2. Schedule a maintenance window → at `starts_at` state shows Maintenance (not Unavailable); after `ends_at` the monitored state returns.
3. As a standard user call `GET /services/{id}/health` → no infra metrics or operations; as a user with `infrastructure.read` they appear.
4. Kill the metrics provider → that section is `unavailable`, rest of the page renders.
