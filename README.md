<p align="center">
  <img src="assets/banner.jpg" alt="Portalab — the self-hosted portal for your community, on your own server" width="100%">
</p>

<p align="center">
  <a href="https://github.com/sharkhunterr/portalab/releases"><img alt="Release" src="https://img.shields.io/github/v/release/sharkhunterr/portalab?style=flat-square&color=3a55d0&labelColor=161b2b"></a>
  <a href="https://hub.docker.com/r/sharkhunterr/portalab"><img alt="Docker pulls" src="https://img.shields.io/docker/pulls/sharkhunterr/portalab?style=flat-square&color=7f9cff&labelColor=161b2b"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-7f9cff?style=flat-square&labelColor=161b2b">
  <img alt="React 19" src="https://img.shields.io/badge/react-19-7f9cff?style=flat-square&labelColor=161b2b">
  <img alt="PostgreSQL 16" src="https://img.shields.io/badge/postgresql-16-7f9cff?style=flat-square&labelColor=161b2b">
</p>

<p align="center">
  <b>One portal for everything your community shares — the media server, the games, the talk — hosted at home.</b>
</p>

---

Portalab gathers what a homelab community lives on into one place its members actually enjoy opening:
what is on the media server and what is coming, what to watch or read next, the trading cards they collect,
the games they play, the wiki and the news, the radio — with profiles, progression and a shop where the
community's own currency is spent. Everything runs on your server, from one Docker image and a PostgreSQL
database, and nothing is sent anywhere you did not connect yourself.

## Highlights

**Media, unified.** One catalog for every service: Plex, Jellyfin, Sonarr, Radarr, Seerr, RomM, Grimmory and
more merge into one page per title, with what is available, requested, downloading or leaving soon. Members
watch in the browser (or cast to a Chromecast), read books and comics, listen to audiobooks, request what is
missing within their quota, and follow a request from the ask to the download.

**Collect and play.** Trading cards cut from the films and series of your own library, opened in boosters
with a scene of their own; a games page with a wheel and mini-games; achievements, quests, levels,
leaderboards and seasonal campaigns. Two currencies earned by taking part — never bought with money — and a
marketplace where the community funds projects together.

**A living community.** Member profiles with frames and name styles, an activity feed, discovery shelves,
events with proposals and votes, a calendar, news with an editorial workflow, a versioned wiki, support
tickets and incident notices, notifications in the portal and by e-mail.

**Yours to shape.** Themes (light, dark and many universes), visual packs that restyle anything from a widget
to the whole interface — safely sandboxed — a dashboard each member arranges, statistics the administrator
declares, automations (when / if / then), plugins, and an optional AI assistant that only ever acts with the
member's own rights.

**Built to be trusted.** Default-deny permissions on every route, roles and groups, privacy controls and data
export for every member, an audit log, rate limits and an intrusion guard, encrypted secrets, and encrypted
backups that move a whole portal to another server. English and French included, more through the
translation tools.

## Integrations

| Area | Services |
| --- | --- |
| Media servers | Plex, Jellyfin, Tautulli |
| Requests and downloads | Seerr (Overseerr, Jellyseerr), Sonarr, Radarr, qBittorrent, Deluge, Maintainerr |
| Libraries | RomM (retro games), Grimmory (books, comics, audiobooks) |
| Metadata | TMDB, TheTVDB, Fanart.tv |
| Radio | SUB/WAVE |
| Infrastructure | Unraid, Glances |
| Search and AI | SearXNG, Ollama and OpenAI-compatible servers, MCP tools |
| Sign-in | Any OpenID Connect provider (Authentik, …) |

Every integration is a connector: a plugin can add more without touching the core.

## Quick start

Portalab ships as one image (`serve`, `worker` and `migrate` entrypoints) next to PostgreSQL 16.

```bash
git clone https://github.com/sharkhunterr/portalab.git && cd portalab/portalab/deploy

# secrets are files, never environment values
mkdir -p secrets
openssl rand -base64 32 > secrets/db_password
echo "postgresql://portalab:$(cat secrets/db_password)@postgres:5432/portalab" > secrets/database_url
openssl rand -base64 48 > secrets/secret_key

docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d portalab worker
```

Open `http://<server>:8080` **from your local network**: the arrival wizard creates the administrator,
sets the portal up and can bring a backup in. Then connect your services in *Administration › Services*.

The image is published as [`sharkhunterr/portalab`](https://hub.docker.com/r/sharkhunterr/portalab)
(`latest` and one tag per release, e.g. `v1.0.0`); `docker-compose.yml` builds it from source when
`PORTALAB_IMAGE` is not set.

## Configuration

Only the bootstrap lives in the environment; everything else is set in the administration and kept in the
database (and in its backups).

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL_FILE` | — | file holding the PostgreSQL URL |
| `SECRET_KEY_FILE` | — | file holding the key that encrypts secrets (32+ bytes) |
| `DATA_DIR` | `/var/lib/portalab` | images, cards, visual packs, plugins, backups |
| `BIND_HOST` / `BIND_PORT` | `0.0.0.0` / `8080` | where the API listens |
| `LOG_LEVEL` | `INFO` | `DEBUG` … `CRITICAL` (JSON logs) |
| `TRUSTED_PROXIES` | `127.0.0.1` | the reverse proxies whose `X-Forwarded-For` is believed |
| `HEALTH_NETWORKS` | local networks | who may call `/healthz`, `/readyz`, `/metrics` |
| `SETUP_NETWORKS` | local networks | where a new (or reset) portal may be set up from |

## On the internet

Put Portalab behind a reverse proxy that terminates TLS (Nginx Proxy Manager, Traefik, Caddy…), declare
that proxy in `TRUSTED_PROXIES`, and keep the first setup on your local network. Single sign-on through
Authentik (or any OpenID Connect provider) links members' accounts automatically. The whole checklist —
proxy settings, Authentik, what to keep private — is in
[`portalab/docs/internet-exposure.md`](portalab/docs/internet-exposure.md).

## Architecture

| Part | Stack |
| --- | --- |
| API and worker | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic — one PostgreSQL schema per module, jobs and events through the database |
| Interface | React 19, TypeScript, Vite, TanStack Query, Radix UI, design tokens, Plus Jakarta Sans and Inter |
| Delivery | one Docker image (read-only, non-root, no capabilities), PostgreSQL 16 |

The code is organised in layers (`core ← capabilities ← modules | connectors ← app`) enforced by
import-linter; plugins and visual packs only see their SDKs. Module guides live in
[`portalab/docs/`](portalab/docs/).

## Development

```bash
# backend — Python 3.12 with uv; integration tests need a PostgreSQL (see portalab/CLAUDE.md)
cd portalab/backend && uv sync
uv run pytest -n auto --dist loadfile
uv run ruff check . && uv run mypy && uv run lint-imports --config importlinter.ini

# frontend — Node 22
cd portalab/frontend && npm ci
npm run lint && npm run typecheck && npm test && npm run build
```

## Releases

Releases are cut from the repository root:

```bash
npm ci                      # release tooling (standard-version)
npm run release:dry         # preview the next version
npm run release:full        # bump, CHANGELOG, tag, push — the tag pipeline does the rest
```

Before releasing, add the new version's notes at the top of [`GITHUB_RELEASES.md`](GITHUB_RELEASES.md)
(`# vX.Y.Z`): they become the GitLab and GitHub release pages, and the release script refuses to run
without them. The tag pipeline validates and tests both halves, builds the image, publishes it to Docker Hub,
mirrors the repository to GitHub and creates both releases (see [`.gitlab-ci.yml`](.gitlab-ci.yml) for the
CI/CD variables it expects).

## Brand

Icon, favicon and banner are drawn from Portalab's own default theme — sources and palette in
[`assets/`](assets/README.md), rendered with `npm run assets`.

<p align="center">
  <img src="assets/icon.jpg" alt="Portalab icon" width="96">
</p>
