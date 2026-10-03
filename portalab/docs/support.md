# Support (spec 016)

Support owns three distinct things — incidents, tickets and feedback — with independent lifecycles.
**Slice A (incidents) is implemented**; tickets and feedback arrive with Slice B (roadmap step 17).

## Incidents (Slice A)

An incident is a declared, service-affecting problem with a public timeline. It is not a ticket: it is
resolved on its own, whatever tickets exist about it.

- Lifecycle `investigating → identified → monitoring → resolved`; every change is an entry of the
  **append-only** timeline (state, severity, public message). Severity `minor | major | critical`.
- Reference `INC-0001` (sequence). Affected services are opaque service ids; viewers only see the
  services they may read (`services.read`).
- Evidence is kept as pointers (`observability:anomaly:<id>`), never payloads.

### The `support.incidents` port

Declared in `portalab.capabilities.health` (shared with Health 006 and Observability 025) and provided
by this module:

| Call | Behaviour |
| --- | --- |
| `create(title=, source=, severity=, evidence=, service_ids=(), dedup_key=None, summary=None)` | idempotent per `(source, dedup_key)` (025 escalations default to the anomaly id); severity also accepts `info|warning|critical` |
| `attach(incident_id, evidence)` | adds an evidence pointer; `None` when the incident is unknown or resolved (the caller opens a new one) |
| `link(service_id, incident_id)` | the incident now shows for that service (006 service page "Incidents" section) |
| `open_for_service(service_id)` / `get(incident_id)` | open incidents of a service / one incident (`None` if unknown) |

`portalab.capabilities.support.testkit` holds `InMemoryIncidents` (for consumers' tests) and the
`IncidentsPortContractKit` both implementations pass.

### API and permissions

| Route | Permission |
| --- | --- |
| `GET /api/v1/incidents?state=open|…&service=` · `GET /api/v1/incidents/{id}` | `incidents.read` (granted to every user) |
| `POST /api/v1/admin/incidents` · `POST …/{id}/updates` · `PATCH …/{id}` · `POST …/{id}/resolve` | `incidents.manage` (support role), audited; `If-Match: <version>` |

Public views never contain evidence pointers, authors or the detailed source. Events
`incident.created|updated|resolved` carry ids and state only.

### Integrations

- Notifications: category `support.incident` through the `notifications.send` port (Notifications 010);
  audience = holders of `incidents.read` on the affected services; critical ⇒ urgent. Until 010 is
  installed nothing is sent.
- Dashboard widget `support.open_incidents`, search provider `incidents`, SPA banner on the home page,
  `/incidents` pages and the `/admin/incidents` console.
