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

## Implementation notes (2026-10-02)
- Extra routes: `POST /connectors/{key}/test` (draft test before saving), `GET /discovery` (candidates).
- `GET /services[/{id}]` returns configuration only to holders of `services.manage` or `infrastructure.read`;
  `services.read` alone sees name, state, health and last sync.
- `POST /services/{id}/sync` and `/resync` enqueue a `connectors.sync_service` job (202); a full resync first
  answers 409 `authz.confirmation_required` with a single-use `confirmation` bound to the request body.
- Enabling runs the compatibility check and the connection test; failures answer 409
  `connector.incompatible` / `connector.test_failed` and leave the state unchanged.
- Connector-provided capability methods are called through the 001 isolation wrapper and return
  `CapabilityResult` (`Available`, `Stale`, `Unavailable`, …).
- Automation action types `connector.sync` and `connector.action` (permission `services.manage`) are declared
  in `portalab.capabilities.automation_actions` for spec 019.
