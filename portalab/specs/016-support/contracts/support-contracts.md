# Contracts — Support

## Ports provided (capabilities)
- **`support.incidents`** (used by 006, 025): `create(title, severity, service_ids, source, dedup_key, evidence_ref?, summary?) -> IncidentRef` (idempotent per `(source, dedup_key)`) · `attach(incident_id, evidence_ref)` · `link(service_id, incident_id)` · `open_for_service(service_id) -> list[IncidentSummary]` · `get(incident_id, viewer)`.
- **`support.tickets`** (for 018/019/012): `get_for_viewer`, `create_from_draft(draft_id, principal)`, `create(request, principal)` (automation/AI act as principal; AI cannot call `create` directly — only draft).
- **`support.knowledge`** (consumed, implemented by 011): `search(query, principal, limit)` · **`gamification.grant_contribution`** (013) · **`community.proposals.create(kind=feature|project, …, provenance=feedback_ref)`** (012; a `project` proposal registers its funding lifecycle in 015 itself): conversion targets (stubs until their specs land) · **`AttachmentScanner`** (optional) · **`DiagnosisFlow`** executed by 018 (tool set: `identify_user`, `get_service_state`, `search_wiki`, `list_open_incidents`, `prefill_ticket_draft`).

## HTTP (`/api/v1`) — Slice A (incidents)
| Path | Permission |
|---|---|
| GET `/incidents?state&service` · GET `/incidents/{id}` | `incidents.read` (default grant; affected services filtered by `services.read`) |
| POST `/admin/incidents` · POST `/admin/incidents/{id}/updates` · PATCH `/admin/incidents/{id}` (severity/services) · POST `…/resolve` | `incidents.manage` (audited; resolve/severity critical = sensitive) |
| POST `/admin/incidents/{id}/tickets/bulk` (comment + optional transition on linked tickets) | `incidents.manage` + `tickets.manage` (audited, confirmation) |
## HTTP — Slice B (tickets, feedback)
| Path | Permission |
|---|---|
| POST `/tickets/precheck` · GET `/tickets/types` | `tickets.create` |
| POST `/tickets` (optionally `draft_id`) · GET `/me/tickets` · GET `/tickets/{id}` · POST `/tickets/{id}/comments` · POST `/tickets/{id}/attachments` · GET `/tickets/attachments/{id}` | create: `tickets.create`; read/comment: requester **or** `tickets.manage` |
| GET `/support/tickets?state&assignee&type&tag&service&q&cursor` · POST `/tickets/{id}/transition` · `/assign` · `/tags` · `/link-incident` · `/internal-notes` | `tickets.manage` (003 catalog name; closing/reassigning another user's ticket and private-data access are sensitive and audited) |
| POST `/diagnosis/runs` (SSE steps) · GET `/diagnosis/runs/{id}` · GET `/tickets/drafts/{id}` | authenticated (AI permission 018); AI failure ⇒ 503 problem, manual path unaffected |
| GET `/feedback/forms` · POST `/feedback` | `feedback.submit` |
| GET `/support/feedback?status&kind` · POST `/support/feedback/{id}/review|dismiss` · POST `…/{id}/convert` (`target_kind`) | `feedback.read` / `feedback.convert[.contribution]` (audited, provenance) |
| GET/PUT `/admin/support/types|workflows|forms[/{key}]` | `support.configure` (audited, versioned) |
Problem codes: `ticket.required_fields_missing` (lists fields), `ticket.transition_forbidden`, `ticket.version_conflict`, `attachment.rejected`, `incident.duplicate`, `feedback.conversion_unavailable`.

## Frontend
Incident banner + `/incidents` page; ticket wizard (precheck → optional AI diagnosis → form), my tickets, ticket detail (timeline/comments/attachments), staff queue/console/bulk, incident console, feedback forms + review/convert screens, admin editors for types/workflows/forms.

## Integrations provided
Search providers (`tickets`, `incidents`, `feedback`) · widgets `support.my_tickets`, `support.open_incidents`, `support.queue` (009) · notification categories `support.*` (010) · palette actions `new-ticket`, `report-bug` (008) · statistics pack `support` (017).
