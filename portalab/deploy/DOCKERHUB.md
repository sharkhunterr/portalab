<p align="center">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/banner.jpg" alt="Portalab" width="100%">
</p>

**Portalab is the front door of your homelab** — the portal your friends and family open instead of a dozen
apps. One catalog for Plex, Jellyfin, Sonarr, Radarr, Grimmory and RomM; requests from the portal and their
status from the ask to the screen ("why is my film still not on Plex?"); a player, a reader and a radio in
the browser; a home dashboard each member arranges with widgets; statistics of everything watched, read and heard; news, newsletters, a wiki, support tickets,
feedback, service status and incidents; a personal dashboard, full personalisation, global search and an AI
assistant. And for those who want to play: XP, levels, quests, mini-games, **Mediacards** cut from your own
library and a marketplace to spend what they earn. Everything is set by the administrator.

<p>
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/home.jpg" alt="The home dashboard each member arranges" width="49%">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/title.jpg" alt="A title's page" width="49%">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/request-journey.jpg" alt="Where a request stands" width="49%">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/statistics.jpg" alt="Statistics" width="49%">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/marketplace.jpg" alt="The marketplace" width="49%">
  <img src="https://raw.githubusercontent.com/sharkhunterr/portalab/main/assets/screenshots/cards.jpg" alt="Mediacards" width="49%">
</p>

Source, documentation and release notes: **https://github.com/sharkhunterr/portalab**

## Tags

| Tag | |
| --- | --- |
| `latest` | the latest release |
| `vX.Y.Z` / `X.Y.Z` | one release |

## Run it

One image, three entrypoints — `serve` (default), `worker`, `migrate` — next to PostgreSQL 16. The
Compose file needs no preparation: on the first start it creates its folders and generates its secrets,
then migrates the database and starts Portalab.

```bash
mkdir portalab && cd portalab
curl -fsSLO https://raw.githubusercontent.com/sharkhunterr/portalab/main/portalab/deploy/docker-compose.yml
docker compose up -d
```

Then open `http://<server>:8080` from your local network: the arrival wizard creates the administrator.

- **Everything in one folder**: `appdata/` next to the file holds Portalab's files, the database and the
  secrets. The secrets are files (`DATABASE_URL_FILE`, `SECRET_KEY_FILE`), never environment values; keep
  `appdata/secrets/portalab/secret_key` safe, it encrypts the credentials of your services.
- **Variables** (port, folder, image tag, reverse proxy) go in a `.env` file next to the Compose file:
  [`.env.example`](https://github.com/sharkhunterr/portalab/blob/main/portalab/deploy/.env.example) lists them.
- **Upgrade**: `docker compose pull && docker compose up -d` — the migrations run before Portalab restarts.
- **Hardened**: read-only filesystem, non-root, every capability dropped.

### On Unraid

With the **Docker Compose Manager** plugin: *Docker › Compose › Add New Stack*, paste the Compose file in
*Edit Stack › Compose File*, set `PORTALAB_APPDATA=/mnt/user/appdata/portalab` in *Edit Stack › ENV File*,
then **Compose Up**. Portalab appears in the Docker tab with its icon and WebUI. The guide:
[On Unraid](https://github.com/sharkhunterr/portalab/blob/main/docs/getting-started.md#on-unraid).

Behind a reverse proxy and on the internet, follow the checklist in the repository
(`portalab/docs/internet-exposure.md`).
