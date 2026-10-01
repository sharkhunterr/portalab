# Research — Portal Observability (spec 025, roadmap step 7)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | **Two-axis component health** (technical: up/latency/error rate; functional: doing its job — lag, freshness, success window, error-rate normality) computed per registered `ObservedComponent` | FR-003..005; "technically up, functionally degraded" is first-class | Single green/red status |
| R2 | **In-process metrics registry** (counters/histograms, labelled) in the kernel; a collector job aggregates to minute samples in `obs.metric_samples`; optional Prometheus-format `/metrics` (admin-token protected) | Homelab-friendly, no mandatory external monitoring (Spec: "no imposed technology") | Mandatory Prometheus/OTel stack |
| R3 | **Structured error recorder** with fingerprinting (component + type + normalized message), occurrence counts, first/last seen, state (open/acknowledged/resolved), redacted context | FR-015/016 | Raw log scraping |
| R4 | **Rule-based anomaly detectors** (error-rate vs rolling baseline, sync duration vs median, repeated automation, stuck consumer, latency spike, repeated failure) with config parameters; detectors are pluggable | OQ-120 default; no ML dependency | Statistical/ML detection |
| R5 | **Observation → Anomaly → Incident** via an `EscalationPolicy` (auto above a severity, otherwise a human validation queue); repeated anomalies with the same fingerprint attach to one open incident; incidents created through the `support.incidents` port | CD-020, no second incident system | Local incident table |
| R6 | **Observability store separate from the business event store** (own partitions/retention); *important* observability events still published through 007 | OQ-124 default, volume/retention differences | Everything into `events.events` |
| R7 | **Performance attribution via phase timers** (`portal_wait`, `external_wait`, `internal`, `timeout`) recorded by middleware, `ConnectorHttpClient` and job runner; no hard-coded thresholds (config) | FR-013/014 | Unattributed latency |
| R8 | **Fail-open**: hooks are non-blocking (bounded in-memory queue, drop-oldest); observability DB/collector failure never fails a request; the Control Center panel reports its own `unavailable` | FR-032 | Synchronous metric writes |
| R9 | **AI observability = metadata only** (counts, latency, errors, provider/model, tools used, actions, failure rate); no prompt/response content in any observability table | FR-012 | Storing conversations for diagnostics |
| R10 | **Diagnostic actions are descriptors** pointing to owning modules' endpoints with their own permission checks; observability never executes foreign actions itself | One owner per action; permissions stay with owners | Embedding foreign logic |
| R11 | **`declare_observable()`** common contribution model for plugins/connectors (metrics, states, checks, errors, tasks, syncs) | FR-034, CD / 023 | Per-plugin monitoring |

No `NEEDS CLARIFICATION` remains; OQ-120..124 use registry defaults.
