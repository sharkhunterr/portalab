# Quickstart — Connectors
1. Configure the `fake` connector as a service, run **test connection** (reports reachability/auth/compat; state unchanged).
2. Enable it → capability available through the registry; a consumer works with it without naming it.
3. Run a sync → `sync_runs` row, `sync.*` events, records delivered to the test sink; run it twice → no duplicates.
4. Make the fake service fail repeatedly → circuit opens, state `unavailable`, data stays readable as stale.
5. Disconnect → capability withdrawn, history retained; purge only through 021.
