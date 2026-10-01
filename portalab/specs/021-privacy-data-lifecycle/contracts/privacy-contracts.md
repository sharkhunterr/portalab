# Contracts — Privacy, Retention & Audit

## Capabilities / ports
- **`VisibilityFilter`** (implements the port declared by 003): `filter(viewer, subject, datum_class, datum_ref, value) -> value | Redacted`; `effective_level(subject, datum_class, datum_ref) -> Level`.
- **`VisibilityPreferenceProvider`** (declared here, implemented by data owners): `get_preference(subject, datum_class, datum_ref) -> Level | None`.
- **`RetentionTarget` registry**: `register_retention_target(...)`.
- **`AggregationGuard`**: `guard(groups, min_size) -> groups_without_small_cells`.
- **Erasure/export** contracts from spec 002 plus `RegistryErasureParticipant(model)`.
- **`AuditQuery`** (read-only): `search(filters, cursor)`; `verify(range)`.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| POST `/privacy/policies`, DELETE `/privacy/policies/{id}` | `privacy.manage` (sensitive, audited) |
| GET `/privacy/policies` | `privacy.manage` |
| GET `/audit`, GET `/audit/export` | `audit.read` (context fields redacted by viewer level) |
| POST `/services/{id}/purge` | `services.purge` (sensitive, audited, confirmation) |
CLI: `portalab audit verify [--from SEQ --to SEQ]`.
