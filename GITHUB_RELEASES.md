# GitHub Releases — Portalab

> Release notes for the GitLab and GitHub release pages. The **first `# vX.Y.Z` block** of this file is what
> the release pipeline posts (`release:gitlab` / `release:github`), and `npm run release` refuses to run
> unless that block is the version about to be released. Write the new block at the top, in English,
> **before** `npm run release:full`; `npm run release:notes` shows what will be posted.
>
> Template:
>
> ```markdown
> # vX.Y.Z
>
> ## Portalab vX.Y.Z — <short title>
>
> <one or two sentences: what this release brings>
>
> ### New
> - **<feature>** — what a member or an administrator can now do.
>
> ### Improved
> - …
>
> ### Fixed
> - **<symptom as users saw it>** — what was wrong, what happens now.
>
> ### Upgrading
> - Migrations run with `docker compose run --rm migrate`; anything else to do.
>
> ---
> ```

---

# v1.0.0

## Portalab v1.0.0 — the first public release

Portalab is the self-hosted portal for your community: the media server, the games, the trading cards, the
wiki, the radio and the people, in one place that runs on your own server. This first public release ships
everything below as one Docker image.

### Media

- **One catalog for every service** — Plex, Jellyfin, Sonarr, Radarr, Seerr, RomM and Grimmory merge into one
  page per title, with what is available, requested, downloading or leaving soon (Maintainerr).
- **Watch, read and listen in the browser** — video with subtitles and Chromecast, books and comics,
  audiobooks; posters refreshed when they change at the source.
- **Requests that explain themselves** — quotas, and a request followed from the ask to the download
  (Seerr, the *arr queues, qBittorrent and Deluge).
- **The radio** — SUB/WAVE's live stream, what plays, and asking its DJ for a song; the player survives a
  page reload.

### Collect and play

- **Trading cards** cut from your own library's films and series, opened in boosters with a scene of their own.
- **Games** — a games page with party games and mini-games.
- **Progression** — levels, achievements, quests, leaderboards and seasonal campaigns; two community currencies
  earned by taking part, never bought with money.
- **Marketplace** — a shop for the community currency and community-funded projects.

### Community and content

- Member profiles with frames and name styles, an activity feed, discovery shelves, events with proposals and votes.
- News with an editorial workflow, a versioned wiki, a calendar, support tickets and incident notices.
- Notifications in the portal and by e-mail; global search across every module.

### Make it yours

- Themes, and **visual packs** that restyle anything from a widget to the whole interface, run in a sandbox.
- A dashboard each member arranges, administrator-declared statistics, automations, plugins.
- An optional **AI assistant** (Ollama or any OpenAI-compatible server, MCP tools) acting only with the
  member's own rights.
- English and French.

### Security

Hardened for the internet, after a full audit and external scans (Semgrep, Bandit, Trivy, Gitleaks, Nuclei,
OWASP ZAP):

- **Behind a reverse proxy** — the proxy is declared (`TRUSTED_PROXIES`); a request a proxy nobody declared
  brings never counts as local, and the server says so in its logs.
- **First setup from the local network only** (`SETUP_NETWORKS`); a crafted backup cannot run SQL or touch
  folders outside the data folder.
- **Sign-in** — attempts throttled per login and per address (lookalike logins included), bounded password
  hashing, an intrusion guard, default-deny permissions on every route.
- **Single sign-on** (Authentik, any OpenID Connect provider) — accounts linked by the server; the
  administrator's only when the provider vouches for the e-mail; a sign-on finishes only in the browser that
  started it.
- **Content** — documents and images that could stall the server are bounded and handled off the event loop;
  only the PNG, JPEG, WebP and GIF decoders read a member's file.
- Strict Content-Security-Policy, sandboxed visual packs, encrypted secrets and backups, no source maps shipped.

### Getting started

```bash
docker pull sharkhunterr/portalab:v1.0.0
```

Follow the quick start in the README: create the secrets, `docker compose up -d postgres`,
`docker compose run --rm migrate`, `docker compose up -d portalab worker`, then open the portal from your
local network to set it up. Going on the internet: see `portalab/docs/internet-exposure.md`.

---
