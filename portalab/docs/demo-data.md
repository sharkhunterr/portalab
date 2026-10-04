# Demo data (manual tests and demos)

Every manual test deployment starts **pre-filled**: `portalab demo seed` creates a lived-in portal through
the modules' own services (accounts, rewards, catalog, purchases, projects, fundings, campaigns, news, wiki,
support, notifications), so business rules, audit, events and the economy ledger stay consistent. It is
idempotent: running it again adds nothing.

```bash
portalab migrate
portalab admin bootstrap --login admin            # once, on a fresh database
portalab demo seed --users-file /secure/path/demo_users
```

On the local-network test instance, `deploy/secrets/lan.sh setup` runs the migrations then the seed.

What it creates:

- **Members** `alice`, `bruno`, `chloe` with random passwords written only to the `--users-file` (mode
  0600, one `login<TAB>password` per line) — never printed or logged;
- **Gamification**: achievements (one hidden), daily/weekly quests, a sign-in reward rule (real use keeps
  earning XP), progression for every account (levels 2–6), unlocked achievements, refreshed leaderboards;
- **Marketplace**: published badges, titles and effects (50–300 Coins), a few already owned;
- **Community projects**: one funded and released, one open with fundings in progress;
- **Campaign**: an active seasonal event with an XP bonus (also visible in the calendar);
- **Content**: published news articles and wiki pages;
- **Support**: tickets and feedback;
- **Notifications**: a welcome broadcast.

Each domain is an independent step: a disabled module or a refused definition is reported as skipped and
the other steps continue (exit code 5 when a step failed). Never run it on a production portal.
