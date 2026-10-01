# Quickstart — Support
1. Admin/Support creates an incident for a service (`investigating`), posts updates through `monitoring` → `resolved`; affected users are notified; the service page shows it (006 section).
2. Observability escalates (validated) via `support.incidents.create` twice with the same dedup key → one incident.
3. A user starts a ticket for the affected service → precheck surfaces the open incident and Wiki suggestions; they continue anyway and the ticket links to the incident; resolving the incident does not auto-resolve the ticket; Support bulk-resolves with a comment.
4. Create a ticket of a type with a required custom field → refusal names the field; with attachment `.exe` → rejected; PNG → stored re-encoded.
5. Agent assigns, transitions per workflow; illegal transition refused; closing another user's ticket requires `tickets.close_any` and is audited; internal notes invisible to the requester.
6. Submit a bug report feedback → not a ticket; staff converts it to a ticket (provenance kept) and to a contribution (once only).
7. Run AI diagnosis (stub) → steps shown as real data vs AI interpretation; a draft is prefilled and nothing is submitted until the user confirms.
