# Quickstart — Gamification & Economy
1. Publish a reward rule (event `media.playback_finished` → 20 XP, 5 Coins); emit the event for user A → one XP and one Coins transaction with rule version; re-deliver the same event → no double grant.
2. Cross a level threshold → `user.level_up` once; Level is displayed, never a balance.
3. Add a campaign modifier x2 and a rule multiplier x1.5 → ×3 applied, capped at `economy.maxTotalBoost`; hit the daily cap → further grants withheld; cooldown blocks rapid repeats; diminishing returns reduce repeats.
4. Spend Coins via the service (stub marketplace) → balance drops; overspend refused; refund creates a new transaction; no row is ever updated or deleted (attempt fails at the DB).
5. Admin grants a manual reward (reason required, audited, marked manual); a rule change creates version 2 effective now and old transactions keep version 1.
6. Final deletion of a user → Coins destroyed by a recorded transaction; ledger rows remain anonymized; user vanishes from leaderboards.
7. Burst of grants over the anomaly threshold → withheld and flagged; admin approves or rejects.
