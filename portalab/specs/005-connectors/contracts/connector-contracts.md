# Contracts — Connectors

## Connector SDK (Python)
```
class Connector:
    key: str; manifest: Manifest(requires_portal, requires_capabilities, permissions)
    config_schema: type[BaseModel]; secret_fields: set[str]
    provides: list[CapabilityBinding]
    async def test_connection(config, secrets) -> TestResult        # reachability, auth, compatibility
    async def discover(targets) -> list[Candidate]                  # operator-supplied targets only
    async def sync(ctx, capability, cursor) -> AsyncIterator[SourceRecord | SyncProgress]
    def provider(capability, service) -> CapabilityProvider         # live calls, wrapped with isolation (001)
```
`SourceRecord{source_system, external_id, kind, payload, observed_at, removed: bool}`.

## Consumer side
`RecordSink` (registered by a module for a capability): `upsert(records, service_ref)` idempotent by (source_system, external_id); `deactivate(...)` for removed; never deletes.

## `ConnectorHttpClient`
Timeouts, max response size, same-host redirect policy, retry/backoff, correlation id, TLS verify option, secret redaction.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/connectors` (catalog) · GET `/services`, `/services/{id}` | `services.read` |
| POST `/services` (configure), PATCH, POST `/services/{id}/test` | `services.manage` |
| POST `/services/{id}/enable|disable|disconnect` | `connectors.manage` (sensitive, audited) |
| POST `/services/{id}/sync` (manual), `/resync` | `services.manage`; full/large-deletion resync = sensitive + confirmation |
| GET `/services/{id}/sync-runs` | `services.read` |
| POST `/connectors/{key}/discover`, `/discovery/{id}/confirm|decline` | `services.manage` |
Problem codes: `connector.incompatible`, `connector.test_failed`, `service.sync_in_progress`, `service.disabled`.
