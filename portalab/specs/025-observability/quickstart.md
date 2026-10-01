# Quickstart — Observability
1. Make the fake connector's sync fail while its probe passes → connector component shows technical `ok`, functional `failing`.
2. Block a consumer → event consumer lag crosses the threshold → anomaly candidate → (policy) incident via the port, one incident for repeated anomalies.
3. Raise the same exception 50 times → one `obs.errors` row with count 50, redacted context.
4. Stop the observability store → requests keep working; the overview panel reports `unavailable`.
5. `/admin/observability/overview` lists problems action-first with diagnostic actions.
