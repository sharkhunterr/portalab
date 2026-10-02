# Connectors (spec 005)

A **connector** is code that knows how to talk to one kind of external service (Plex, Radarr, …); a
**service** is a configured instance of it. Connectors ship as packages (`portalab.connectors.<key>`) or
plugins and implement the SDK in `portalab.capabilities.connector_sdk`; they never import modules and
never write module tables.

## Writing a connector

```python
class MyConnector:
    key = "mine"; name = "My service"
    manifest = Manifest(version="1.0.0", requires_portal=">=0.1,<2",
                        requires_capabilities=(), permissions=())
    config_schema = MyConfig            # pydantic model, non-secret fields only (e.g. base_url, verify_tls)
    secret_fields = frozenset({"api_token"})
    provides = (CapabilityBinding(MY_CAPABILITY_SPEC, syncable=True),)

    async def test_connection(self, service: ServiceHandle) -> TestResult: ...
    async def discover(self, targets): ...          # probe ONLY the operator-supplied targets
    async def sync(self, ctx, cursor): ...          # yield SourceRecord / SyncProgress(cursor)
    def provider(self, capability, service): ...    # live provider for the capability protocol
    def actions(self): ...                          # optional idempotent actions (automations)
```

* HTTP goes through `service.http` (`ConnectorHttpClient`): timeouts, response-size cap, same-host
  redirects, bounded retries for idempotent calls, optional TLS verification, correlation id, and error
  text with registered secrets redacted.
* `SourceRecord.observed_at` is the time the **source** observed the item, never the sync time.
* Removed items are reported as `SourceRecord(..., removed=True)`; the runner deactivates them only when
  the whole run succeeds.
* Every connector must pass `portalab.connectors.conformance.ConformanceKit` in CI (see
  `tests/contract/connectors/test_conformance_fake.py`).

## Consuming data: `RecordSink`

A domain module registers one sink per capability (`portalab.capabilities.record_sink.register_sink`).
Sinks upsert idempotently by `(source_system, external_id)`, ignore older observations, deactivate instead of
deleting and keep provenance; only the explicit 021 purge (`services.purge`) erases a service's rows
(`purge(service_ref)`). Prove a sink with `RecordSinkContractKit` (`portalab.capabilities.record_sink_testkit`).

## Field priority (CD-026, F7)

When several sources describe the same item, `FieldPriorities.reconcile()` picks each field from the
first source of the consuming domain's priority list — **`media.fieldPriority.<kind>.<field>`** (owned and
declared by Media, spec 024), read through the `admin.config` reader — then any default order, then the
remaining sources by name. Entries name a connector (`"plex"`) or one service (`"plex:<service id>"`).
Connectors declare no priority setting of their own; an undeclared key means "no preference". The winning
source of every field is returned as provenance.

## Service lifecycle

`configured → enabled` (after a passing compatibility **and** connection check) `⇄ error | unavailable |
maintenance` (conditions; the per-service circuit breaker moves a service to `unavailable` and back)
`→ disabled` (re-enable possible) and any state `→ disconnected` (final; credentials erased, history and
imported data kept and shown as historical). Capabilities are provided only while active; during a
condition calls are short-circuited to the last known data (`Stale`). "Syncing" is a sync status
(`sync_state.status`), reported apart from health.

## Synchronization

* Scheduled: the `connectors.sync_due` sweep (every minute) enqueues `connectors.sync_service` per due
  service, deduplicated per `(service, window)`; manual syncs, resyncs and the `connector.sync` automation
  action use the same job kind.
* One run per service at a time (PostgreSQL advisory lock): an overlapping scheduled run is skipped, a
  manual one gets `service.sync_in_progress`.
* A failing sink batch fails the run without rolling back earlier batches; nothing is deactivated by a
  failed or partial run. Runs are written once to the immutable `connectors.sync_runs` history.
* Resync: `partial` re-reads from scratch; `full` also deactivates this service's records the source no
  longer lists (never native data or other services' rows). A full resync needs a confirmation; one that
  would deactivate more than `connectors.resync.confirmDeleteRatio` is held (`deletion_confirmation_required`)
  until re-requested with `allow_large_deletion`.

## Permissions

| Action | Permission |
|---|---|
| List connectors, services (name, state), sync history | `services.read` |
| See service configuration and diagnostics | `services.manage` or `infrastructure.read` |
| Configure, test, sync, resync, discover | `services.manage` |
| Enable, disable, disconnect | `connectors.manage` (sensitive, audited) |
| Purge a service's imported data | `services.purge` (spec 021) |
