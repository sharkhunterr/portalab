# Support (spec 016)

Support owns three distinct things — incidents, tickets and feedback — with independent lifecycles.
Slice A (incidents) and Slice B (tickets, feedback, conversion, assistant diagnosis) are implemented.

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

## Tickets (Slice B)

A ticket is one user's request. It has a **type** (custom fields), pins the **workflow version** it started
with, an optional link to **one** incident, comments (internal notes are staff-only), attachments, tags and
an **append-only history**; every change writes the ticket (`version`), its history entry and its event in
one transaction, and mutations accept `If-Match: <version>` (409 `ticket.version_conflict`).

### Workflows

Workflows are data with a closed schema — states (`kind`: `open|active|waiting|resolved|closed`,
`terminal`) and transitions (`from`, `to`, `who`: `requester|assignee|staff`, `comment_required`,
`reopen`). No scripting; reactions to transitions are events (019). The baseline:
`open → in_progress ⇄ waiting_user → resolved → closed`, `reopen` (requester, within
`support.reopenWindowDays`), `cancel`. Custom workflows are validated (unknown states, unreachable states and
dead ends are refused) and saved as new versions (`PUT /admin/support/workflows/{key}`).

### Ticket types

Fields: `text|long_text|select|multi_select|number|boolean|date|user`, `required`, `options` and
`visibility` (`requester_and_staff` or `staff_only`). Creating a ticket without a required field answers
422 `ticket.required_fields_missing` naming the fields. Baseline types: `bug`, `access_request`,
`service_issue`, `question`, `other` (seeded idempotently; edit at `/admin/support`).

### Attachment policy

The shared `portalab.core.uploads` helper: type from magic bytes against `support.attachments.allowedTypes`
(png, jpeg, webp, pdf, text by default — executables renamed `.png` are refused), size ≤ `maxBytes`,
≤ `maxPerPost` per post, images re-encoded without EXIF, sanitized names, then the optional
`support.attachment_scanner`. Only images are served inline; everything else downloads with `nosniff` and a
sandboxing CSP. Private (staff) attachments are staff-only.

### Before a ticket: precheck

`POST /tickets/precheck` returns open incidents matching the service or the text and permitted wiki pages
(`support.knowledge`, spec 011) — deterministic, no AI; each section degrades on its own. Duplicates are
**linked** to the incident (no ticket merge); resolving an incident never touches tickets — staff may run an
audited, confirmed bulk action (`POST /admin/incidents/{id}/tickets/bulk`, comment + optional transition,
per-ticket outcome).

### Permissions

`tickets.create` (users) · requester or `tickets.manage` to read/comment · staff console
(`/support/tickets`, transition/assign/tags/link-incident/internal notes) needs `tickets.manage`;
reassigning someone else's ticket and closing a requester's ticket are audited · `support.configure` for
types, workflows and forms.

## Feedback and conversion

Forms (`general`, `bug_report`, `feature_request`, editable) produce feedback items — never tickets by
themselves. Staff with `feedback.read` review or dismiss; conversions are explicit and go to the owning
domain through ports: `ticket` (here), `contribution` (Gamification 013, `feedback.convert.contribution`),
`feature_proposal` / `community_project` (Community 012). Each target is created once per feedback
(provenance in `feedback_conversions`); contribution and community project conversions ask for a
confirmation; a target whose owner is not installed is offered disabled with its reason.

## Assistant diagnosis contract

`POST /diagnosis/runs` streams steps (SSE): identify the user, service state (006), open incidents, wiki pages
the user may read and the assistant may use — **real data** with `as_of` — then `analyze` and `propose` —
**assistant interpretation** from the `support.diagnosis_executor` port (provided by 018), run as the
requesting user — and finally a `ticket_draft` (TTL `support.draftTtlMinutes`). Nothing is submitted: the
user reviews the prefilled form and sends `POST /tickets` with `draft_id`. No executor or a failure ⇒ 503
`diagnosis.unavailable`; the manual path is unaffected. The AI channel can never create a ticket directly.

## Integrations

Search providers `tickets` (own for users, all for staff) and `feedback` (staff); widgets
`support.my_tickets`, `support.queue`; palette actions `support.new_ticket`, `support.report_bug`;
statistics pack `support`; notification categories `support.assignment|ticket_status|feedback|incident`;
019 action types `ticket.create` and `incident.create` (run as the rule's author, same rules).

## Privacy

Ticket text, comments, attachments, drafts, diagnosis runs and feedback are personal. Erasure tombstones the
requester, removes staff-only fields, deletes the user's attachments, drafts and runs and anonymizes
authorship; histories stay (append-only, anonymized). Retention (`support.ticketRetentionMonths`) anonymizes
closed tickets and old feedback.
