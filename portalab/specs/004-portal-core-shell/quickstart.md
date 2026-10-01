# Quickstart — Shell & Navigation
1. Log in as a user lacking `media.*` → the Media entry is absent from nav and palette; opening `/media` shows the unauthorized state.
2. Disable a module in Administration → navigation updates live (SSE) and its route shows "unavailable".
3. Register a malformed contribution in a test plugin → rest of nav unaffected; diagnostic visible to the Admin.
4. Press `Mod+K` → palette lists only permitted destinations/actions; `Esc` returns focus.
5. Resize to 360 px → drawer navigation exposes the same destinations; search and AI entries remain reachable.
6. Kill the AI endpoint → AI entry shows unavailable; search and navigation keep working.
