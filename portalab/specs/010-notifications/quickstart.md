# Quickstart — Notifications
1. Call `send` for a user with a category they muted on portal → suppressed(preference); mute only email → portal still delivers.
2. A critical alert reaches a user who muted the category (portal only), is not coalesced, and the toast persists until acknowledged; reduced motion removes animation; sound off silences the cue.
3. Remove the recipient's permission on the subject before delivery → delivery suppressed(permission_lost).
4. Schedule a maintenance → J-1 and H-1 jobs created; reschedule → old ones cancelled, corrective message sent to already-notified users; cancel → corrective message; `maintenance.started` → immediate alert; replays create no duplicates.
5. Send the same dedup key twice → one communication.
6. Configure SMTP (test mode), enable email for a category → outbox sends; kill SMTP → portal delivery unaffected, email retries then `failed` visible to the Admin.
