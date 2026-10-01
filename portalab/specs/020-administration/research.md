# Research — Administration & Configuration (spec 020, roadmap step 4)

Roadmap step 4 = the **transversal configuration system** (CD-011) plus the Control Center skeleton. Other administrable domains plug into it as their specs land.

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Single configuration store** (`config.settings` with scope rows) behind a `ConfigService`; hierarchy resolution Global → Module → Plugin → User; settings declared in code via the kernel `declare_setting` (contract from 001) | CD-011; one engine | Per-module config tables; env-file config for product settings |
| R2 | **Resolution is a pure function**: `effective(key, user?) = apply(policy constraints, user value ▸ plugin ▸ module ▸ global ▸ code default)`; admin policy can *lock* or *bound* a key; the user's stored value is **retained** when policy overrides it | FR-013/014 of spec 020, CD-016 pattern | Overwriting user values on policy change |
| R3 | **Typed, versioned schemas** (Pydantic models per setting; `version` int; migrations of stored values via registered upgrade functions) | Config must survive updates without silent resets | Untyped JSON blobs |
| R4 | **Sensitive settings encrypted** with `core.secrets`, write-only through the API, redacted from audit/log | Secrets never exposed | Plaintext |
| R5 | **Preview/validate/apply** as a two-phase API: `POST /admin/config/validate` returns effective-value diff + warnings, `apply` commits and emits `admin.config_changed`; changes carry the actor and previous value in audit | FR-012 | Apply-only |
| R6 | **Control Center = aggregation API** (`/admin/overview`) built from **panel providers** registered by each module (health, sync, incidents, tickets, automations, AI, infra, storage, required actions); each panel loads independently and degrades alone | Control Center principle; panels arrive as modules land | A monolithic overview query |
| R7 | **Required actions** = items contributed by providers (`RequiredActionProvider`), prioritized action → impact → criticality → age | Spec FR-002; no invented rules | Hard-coded list |
| R8 | **First-run wizard** = thin UI/API over `IdentityBootstrap` (002) + config validation; locked after completion; re-run needs explicit audited reset (OQ-98 default) | One bootstrap path | Separate seeding |
| R9 | **Import/export of configuration** as a versioned signed-less JSON document (secrets excluded); import = validate → conflict report → apply | FR-016 | Direct DB dump |
| R10 | **Backup/restore & update/migration are operator CLI + admin read-only status in this step** (`portalab backup`, `portalab restore`, `portalab migrate`); UI-triggered restore deferred until backup scope is decided (OQ-96) | Avoid inventing restore semantics | UI restore now |
| R11 | **Module/plugin/connector enable-disable** is a generic `Toggle` service writing config + emitting events; navigation updates from the registry (004) | FR-014/015 | Per-domain toggles |

No `NEEDS CLARIFICATION` remains; OQ-95..99 use registry defaults.
