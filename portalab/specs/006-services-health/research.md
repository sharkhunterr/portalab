# Research — Services & Health (spec 006, roadmap steps 6b and 13)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Service State is derived, not set**: `StateDeriver` combines probe samples, breaker state (005) and active maintenance into one of Operational/Degraded/Unavailable/Maintenance/Unknown; stale monitoring ⇒ Unknown, never Operational | FR-001..003 | Manual state flags |
| R2 | **Probes are a capability** (`service.health_probe`) provided by connectors; a scheduler job per service writes `health_samples`; thresholds (consecutive failures, latency, staleness) are admin config | Capability decoupling (CD-019) | Hard-coded ping in the module |
| R3 | **Five concepts stay separate in data and API**: Service State (here), Incident (lifecycle in Support 016 via a port), Maintenance (owned here, CD-020), Ticket (016), Sync State (005) | FR-004 | One status field |
| R4 | **Maintenance windows owned here**: schedule/start/end by absolute instants; jobs flip state at instants; events `maintenance.*` feed Calendar (011) and Notifications | CD-020 | Maintenance in Calendar |
| R5 | **Infrastructure metrics via capability `infrastructure.metrics`** (cpu, ram, storage, gpu, network, temperature, transcoding), each metric with its own availability; time series in `infra_samples` (short retention, partitioned); gated by `infrastructure.read` | FR-013..015 | Always-on collection of every metric |
| R4b | **Server operations via capability `server.operations`** (list/execute); always sensitive, confirmation, audited; permission `services.manage` plus per-operation flag | FR-016..018 | Ad-hoc shell access |
| R6 | **Uptime/availability from hourly rollups** (`health_rollups`) computed by a job; raw samples pruned early | Efficient history view | Query raw samples |
| R7 | **Service detail = independent sections API**: each section (state, availability, errors, maintenance, incidents, tickets, sync, infra, history) resolved separately with its own state and permission filter; standard vs privileged shapes enforced server-side | FR-010/026..029 | One monolithic call |
| R8 | **Incident lifecycle is consumed through `support.incidents` port**; 006 creates/links incidents and displays them; the implementation lands with Support 016 (incident phase scheduled at roadmap step 13) | One incident system | Local incident table |

No `NEEDS CLARIFICATION` remains; OQ-25..29 use registry defaults (admin thresholds; standard users see state+availability; uptime/last error/infra need permission).
