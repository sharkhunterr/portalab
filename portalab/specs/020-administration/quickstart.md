# Quickstart — Administration & Configuration
1. First run: open the app → wizard creates the sole Admin and validates the base settings; afterwards the wizard answers 410.
2. `PUT /admin/config` a Global value, then a User preference bounded by a policy → `GET /me/preferences` shows the effective value and `locked`.
3. Remove the policy → the user's retained preference is effective again.
4. Disable a plugin toggle → data remains, navigation drops its entries (once 004 lands).
5. Export then re-import configuration → conflict report, no secrets in the file.
