# Quickstart — Campaigns
1. Create "Halloween": window Oct 20–Nov 1 (yearly, tz Europe/Paris), modifiers (horror movie ⇒ XP x2 + Coins x1.5; title contains "Halloween" ⇒ XP x2), theme, an achievement and a quest; simulate a horror film titled "Halloween Night" → both XP modifiers match once each.
2. At the start instant the scheduler opens an interval and emits `campaign.started`; a finished horror movie at 21:00 local is boosted; the same event delivered late (after the campaign ended) still resolves by `occurred_at`.
3. Gamification combines campaign + rule multipliers multiplicatively with the cap; cooldown/caps still bound rapid repeats; the same occurrence never double-grants.
4. Admin deactivates mid-window (reason, confirmation) → modifiers stop at once, logged; schedule resumes at the next occurrence/start; reactivation records a new interval.
5. Edit the campaign while active → new version effective now; grants made earlier keep the old version; history shows both.
6. Stop the media provider → conditions needing genre evaluate unknown → no boost, no crash, diagnostics counter increments.
7. Campaign theme overlays only if allowed by policy and user preference; high contrast/reduced motion still win.
