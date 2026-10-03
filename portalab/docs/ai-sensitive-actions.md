# AI sensitive actions (spec 018 T018)

Every AI tool declares a sensitivity; the portal **validates it against the permission registry (003)**,
so a tool cannot under-declare.

| Sensitivity | Behaviour |
|---|---|
| `read` | runs when the user may (AI principal re-authorized before the call) |
| `write` | runs when the user may; the domain service applies its own rules and emits its own events with the AI actor acting for the user |
| `sensitive` | never runs inline: a **pending action** is created with the exact parameters, a parameters hash and a tool-generated summary; the user confirms or declines it in the portal before it expires (`ai.pendingActionTtlMinutes`, default 10) |
| `ai_forbidden` | never offered to, nor executable by, the assistant — even for the Admin |

## Automatic upgrades

* A permission declared with `requires_confirmation` (e.g. `news.delete`, `wiki.delete`, `services.manage`,
  `rewards.grant`, `economy.manage`, `events.manage`) makes any tool using it `sensitive`.
* These permissions make a tool `ai_forbidden`: `ai.manage` (assistant configuration),
  `users.admin.transfer` (Admin transfer), `users.roles.manage` (roles and grants), `security.manage`
  (security/visibility policies), `events.manage` (event-store mutation). Secrets and credentials are never
  exposed through tools.

## Confirmation rules

* Only the action's owner, **from a user session** (CSRF-protected), can confirm or decline
  (`POST /api/v1/ai/actions/{id}/confirm|decline`); the AI channel is refused; other users get 404.
* Confirmation consumes a single-use token of the authorization `ConfirmationService`, bound to the
  permission and the parameters hash; tampered parameters are refused.
* The tool runs **once** (a second confirmation returns the stored outcome); declined or expired actions
  never run; a periodic job marks expired actions.
* Audit: `ai.action_proposed`, `ai.action_confirmed`, `ai.action_declined` with the tool, ids and the
  parameters hash — never the conversation text. Events `ai.action_confirmed|declined|expired` carry ids.
