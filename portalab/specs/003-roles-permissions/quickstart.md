# Quickstart — Authorization (target behaviour)
1. Migrate; start the app: declared permissions appear in `authz.permissions`.
2. Bootstrap the Admin (spec 002). Admin can list roles/permissions; a plain user gets 403 on `/roles`.
3. Grant a role to a user → effective on the very next request; revoke → denied immediately.
4. Try to grant a reserved permission to `editor` → `authz.reserved_permission`.
5. Run two concurrent Admin transfers → exactly one succeeds; Admin count stays 1.
6. Perform a sensitive action allowed and denied → two rows in `audit.audit_entries`; UPDATE/DELETE on that table fails.
