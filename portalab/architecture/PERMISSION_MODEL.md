# Permission Model

## Principle
Deny by default. Permissions are server-side.

User → Roles → Permissions → Context → Decision

Conceptual form:
domain.action.scope

Examples:
users.read
users.manage
tickets.create
tickets.manage
wiki.edit
news.publish
marketplace.manage
economy.manage
events.manage
services.read
services.manage
infrastructure.read
automation.manage
ai.use

Base roles:
- User
- Support
- Moderator
- Editor
- Admin

Exactly one Admin account.

Plugins can declare permissions.

Privacy is separate from permission.

AI is not a role; it operates under the current user's effective permissions.

Sensitive operations include deletion, permission changes, significant refunds, economy-rule changes and destructive service/data actions.
