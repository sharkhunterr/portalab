# GitHub Releases — Portalab

> Release notes for the GitLab and GitHub release pages. The **first `# vX.Y.Z` block** of this file is what
> the release pipeline posts (`release:gitlab` / `release:github`), and `npm run release` refuses to run
> unless that block is the version about to be released. Write the new block at the top, in English,
> **before** `npm run release:full`; `npm run release:notes` shows what will be posted. The version that
> block announces is the one released when it is above the current one (a major or minor release is chosen
> by writing its notes); otherwise the commits decide (`feat` → minor, `fix` → patch).
>
> Every release after v1.0.0 lists the GitLab issues it closes, sorted by kind: `npm run release:issues`
> prints them (security, fixed, new, documentation and tooling, improved) — rewrite each title in English,
> as a member or an administrator would read it, keeping its `#123`. The release script refuses notes
> without a `### Closed issues` part (v1.0.0, the first public release, is the exception).
>
> Images are absolute links pinned to the tag (`https://raw.githubusercontent.com/sharkhunterr/portalab/vX.Y.Z/assets/screenshots/<name>.jpg`):
> release pages do not resolve relative paths.
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
> <a screenshot of the headline feature, when there is one>
>
> ### Highlights
> - **<feature>** — what a member or an administrator can now do.
>
> ### Closed issues
>
> #### Security
> - <what was exposed, what is closed now> (#123)
>
> #### Fixed
> - <the symptom as users saw it — what happens now> (#124)
>
> #### New
> - <what members or administrators can now do> (#125)
>
> #### Documentation and tooling
> - … (#126)
>
> #### Improved
> - … (#127)
>
> ### Upgrading
> - Migrations run with `docker compose run --rm migrate`; anything else to do.
>
> ---
> ```

---

# v1.0.0

## Portalab v1.0.0 — the front door of your homelab

**Portalab is the portal your friends and family open instead of a dozen apps.** One catalog for every media
service, requests that explain themselves, a player, a reader and a radio in the browser, statistics of
everything they watched, read and heard, news, a wiki and support — and, for those who want it, a whole
game on top: levels, quests, mini-games, collectible cards cut from your own library and a shop to spend
what they earn. One Docker image, one PostgreSQL database, your server. Every feature is set by the
administrator.

![Portalab's home: each member's own dashboard](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/home.jpg)

### A home page that shows everything at a glance

Portalab opens on **a dashboard each member builds**: what to continue, what arrived since the last visit,
a title for tonight, whether every service is up, the wheel of the day, the calendar, the radio, requests,
quests, statistics… Add, arrange and resize widgets, with a layout of its own on the phone — or keep the
one the administrator prepared.

### Everything on the media server, in one place

- **One catalog** for Plex, Jellyfin, Sonarr, Radarr, Grimmory and RomM: films, series, music, books,
  comics, audiobooks and retro games — one page per title, available, coming, requested or leaving soon.
- **Ask from Portalab** — search any film or series and request it in one click, within your quota
  (Overseerr / Jellyseerr).
- **"Why is my film still not on Plex?" — answered.** Every request is followed from the ask to the
  screen: approved, released, searched, downloading (with the torrent's real state), imported, available —
  each step in plain words, and the assistant can explain it.
- **Watch, read and listen in the browser** — video with subtitles and Chromecast, EPUB/PDF/comics reader,
  audiobook player that remembers where you stopped.

![A title's page](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/title.jpg)
- **The radio** — SUB/WAVE live, what plays, ask the DJ for a song; the player follows you across pages.

![Where a request stands](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/request-journey.jpg)

### Statistics of everything you watch, read and hear

Time spent, plays, favourite titles, hours and weekdays, genres, cast, decades, devices and quality — films,
series, live TV, music, books, audiobooks, radio and games, each tab shown only when a service of yours
feeds it. Yours or the whole server's, over any period, plus a yearly recap.

![Statistics](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/statistics.jpg)

### A game — for those who want to play

Optional for every member: play it all, play without the cards, or don't play.

- **XP, levels, coins and contribution** from watching, reading and listening, from requests, and from
  taking part (news, wiki, tickets, feedback, events); quests, achievements, streaks, leaderboards and
  seasonal campaigns.
- **Mini-games** from your own library — the daily wheel, the title of the day, the blurred scene, the cast,
  the hidden synopsis, higher or lower, the timeline — alone or in a party.
- **Mediacards** — collect your favourite films and series as trading cards cut from your library, opened
  from boosters in a scene of their own.
- **The marketplace** — spend what you earn (never real money) on interfaces, palettes, frames, name
  styles, badges, effects, and on features: statistics tabs, extra requests, radio requests, widgets,
  access to content. Community projects funded together.

![Mediacards](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/cards.jpg)

![The marketplace](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/marketplace.jpg)

### Community, content and help

- **News** with an editorial workflow and **newsletters by e-mail**; an **internal wiki**, versioned; a
  **calendar**; events and proposals voted by the community; profiles and an activity feed.
- **Terms of use** published in versions and accepted by every member.
- **Support tickets**, **feedback** (bug reports, suggestions, surveys and review forms with the team's
  answers), **service status** for every connected service and **incidents** that say what broke and when
  it was fixed.

### Yours to shape

- **Full personalisation** — interface, palette, light or dark, profile, language, notification
  preferences per topic, in the portal and by e-mail; **guided tours** of every part.
- **Global search** across media, people, wiki, news, tickets and products — exact or by meaning.
- **An AI assistant** (Ollama or any OpenAI-compatible server, MCP tools) acting only with the member's own
  rights.
- **For administrators** — every module, reward, price, quota, theme, page and permission is set from the
  administration; themes and sandboxed visual packs, automations, plugins, backups, audit, alerts.

![The administration's control center](https://raw.githubusercontent.com/sharkhunterr/portalab/v1.0.0/assets/screenshots/admin.jpg)

### Connects to your stack

Plex · Jellyfin / Emby · Tautulli · Overseerr / Jellyseerr · Sonarr · Radarr · qBittorrent · Deluge ·
Maintainerr · Grimmory · RomM · SUB/WAVE · TMDB · TheTVDB · fanart.tv · SearXNG · Ollama and
OpenAI-compatible servers · Authentik and any OpenID Connect provider · Unraid · Glances.

### Ready for the internet

Audited and scanned (Semgrep, Bandit, Trivy, Gitleaks, Nuclei, OWASP ZAP) before this release:
reverse-proxy aware (`TRUSTED_PROXIES`), first setup from the local network only, throttled sign-in and an
intrusion guard, default-deny permissions on every route, single sign-on with accounts linked by the
server, strict Content-Security-Policy, sandboxed visual packs, encrypted secrets and backups.

### Getting started

```bash
docker pull sharkhunterr/portalab:v1.0.0
```

Follow the [quick start](https://github.com/sharkhunterr/portalab#quick-start): create the secrets,
`docker compose up -d postgres`, `docker compose run --rm migrate`, `docker compose up -d portalab worker`,
then open the portal from your local network to set it up. The
[documentation](https://github.com/sharkhunterr/portalab/tree/main/docs) covers members, administrators and
going on the internet.

---
