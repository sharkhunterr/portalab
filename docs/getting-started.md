# Getting started

Install Portalab with Docker Compose, set it up with the arrival wizard, and keep it up to date.

Portalab ships as **one Docker image** with three entrypoints, next to a **PostgreSQL 16** database:

| Entrypoint | What it does |
| --- | --- |
| `serve` (default) | The web interface and the API, on port `8080` |
| `worker` | Background jobs: synchronising services, health probes, notifications, scheduled tasks |
| `migrate` | Creates or upgrades the database schema, then exits |

You run `migrate` once per install or upgrade, and keep `serve` and `worker` running side by side.

## Requirements

- A Linux host with **Docker** and the **Docker Compose** plugin (`docker compose`).
- `openssl` (or any other way to generate random strings) to create the secrets.
- Disk space for the database and the data volume. Posters, artwork and the trading cards' images fetched from your services can grow to several gigabytes.
- A browser on the **same local network** as the server for the first setup (see [The arrival wizard](#the-arrival-wizard)).

You do not need to install PostgreSQL yourself: the Compose file runs the official `postgres:16-alpine` image.

## Install with Docker Compose

The reference Compose file is [`portalab/deploy/docker-compose.yml`](../portalab/deploy/docker-compose.yml).

### 1. Get the deployment files

```bash
git clone https://github.com/sharkhunterr/portalab.git
cd portalab/portalab/deploy
```

By default, `docker-compose.yml` **builds** the image from source (`portalab:local`). To run the published image instead, create a `.env` file next to `docker-compose.yml`:

```env
PORTALAB_IMAGE=sharkhunterr/portalab:latest
```

The image is published as [`sharkhunterr/portalab`](https://hub.docker.com/r/sharkhunterr/portalab), with `latest` and one tag per release (for example `v1.0.0`). Pin a release tag if you prefer to upgrade on your own schedule.

### 2. Create the secrets

Portalab never reads its secrets from plain environment values: they are **files**, mounted as Docker secrets.

```bash
mkdir -p secrets
openssl rand -base64 32 > secrets/db_password
echo "postgresql://portalab:$(cat secrets/db_password)@postgres:5432/portalab" > secrets/database_url
openssl rand -base64 48 > secrets/secret_key
```

| File | Used by | Content |
| --- | --- | --- |
| `secrets/db_password` | PostgreSQL | The database password |
| `secrets/database_url` | Portalab (`DATABASE_URL_FILE`) | The PostgreSQL connection URL |
| `secrets/secret_key` | Portalab (`SECRET_KEY_FILE`) | The key that encrypts stored credentials (at least 32 bytes) |

> **Keep `secret_key` safe and never change it.** The passwords, API keys and tokens of your connected services are encrypted at rest with a key derived from it. Without the same key, they cannot be read again.

### 3. Start the database, migrate, start Portalab

```bash
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d portalab worker
```

The containers run hardened by default: read-only filesystem, a scratch `/tmp` only, no new privileges, every Linux capability dropped. Portalab writes only to its data volume (`portalab-data`, mounted at `/var/lib/portalab`).

To change the published port, the log level or the reverse-proxy settings, see [Configuration](configuration.md).

### 4. Check it is running

```bash
docker compose ps
docker compose logs -f portalab
```

The image has a built-in health check on `/healthz`. You can also run a read-only check of the deployment (who Portalab runs as, whether its code and folders are protected, whether plugins can be confined):

```bash
docker compose run --rm portalab doctor
```

## The arrival wizard

Open `http://<server>:8080` in a browser **on your local network**. A new portal shows its arrival wizard: a full page of its own that sets everything up before anyone else can see the portal.

> The wizard only answers requests from the local networks (`SETUP_NETWORKS`). A portal that is not set up yet cannot be claimed from the internet. Set it up from home first, then put it behind your reverse proxy. See [Configuration](configuration.md#who-may-reach-what).

### Prepare

1. **Welcome**: choose the portal's language (the members' default, which each one can change), then how it is installed:
   - **New installation**: start from scratch.
   - **Import another Portalab**: bring in a backup archive of an existing portal (see [Backups and restore](#backups-and-restore)).
2. **Identity**: the portal's name (left empty, it is called Portalab), an optional tagline, the optional name of the portal's currency (singular and plural), and the time zone. All of it can be changed later in *Administration › Site identity*.
3. **Features**: keep what your community needs. Each feature brings what it depends on, and nothing is ever deleted: a feature switched off can be switched on again later from the setup assistant or *Modules*.

   | Group | Features |
   | --- | --- |
   | Media | Media |
   | Content and communication | Wiki, News, Newsletters, Calendar |
   | Help and support | Tickets, Incidents, Services' status, AI assistant |
   | Play | XP, levels and quests; Shop |
   | Tools | Automations, Statistics, Dashboard, Search |

4. **Administrator**: your login, a password of at least 12 characters, a display name and an optional e-mail. This account holds every right on the portal.
5. **Summary**: check everything. Nothing is written before you select **Create the portal**.

The wizard then creates the account, signs you in, applies the identity and sets up each feature, with a progress screen.

### Set up (signed in)

Without leaving the wizard, you continue at `/setup`. Each step can be skipped and picked up later.

| Step | What you do |
| --- | --- |
| Services | Connect Plex, Jellyfin, Seerr, Radarr, Sonarr and the rest. Every connection is tested before it is saved. See [Services and integrations](admin/services.md). |
| Requests | Shown once Seerr is connected: how many films and series each member may request, and over how many days. |
| Members | The accounts your services know: create the missing members and link each one to their accounts. |
| Access | **Open sign-up** (anyone, verified by e-mail) or **By invitation** (you create the accounts, or they come from your services). |
| E-mail | The e-mail server, for account verification, forgotten passwords and newsletters. Optional. |
| Look | The default interface members see, and those they may choose. |
| Game | XP, levels, achievements, quests, campaigns and the shop: take the recommended install, adjust it, or build everything yourself. Shown if you kept Play. |
| AI assistant | Optional: an OpenAI-compatible provider (local like Ollama, or hosted), its model and its key. Shown if you kept the AI assistant. |

The last screen opens your portal. Whatever you skipped waits in *Administration › Setup assistant*, which shows every step, what is ready and what is left. Your progress is kept, so you can run it again at any time.

> **Alternative from the command line.** `docker compose run --rm portalab admin bootstrap --login <login>` creates the sole administrator of a fresh portal and prompts for the password (or reads it from `--password-file`).

## Signing in

Members sign in on the portal's sign-in page with their **login** and **password**. Repeated failed attempts are slowed down ("Too many attempts. Try again in…").

When single sign-on is set up (Authentik or any OpenID Connect provider), the page also offers **Sign in with {provider}**, with the portal password as a fallback. Single sign-on links accounts on the server side: a provider account signs in as the member it is linked to, or the member with the same e-mail, or a new member when account creation is allowed. Set it up in *Administration › Configuration* (Members & access); see [Members and roles](admin/members-and-roles.md) and the [internet exposure guide](../portalab/docs/internet-exposure.md#4-authentik-single-sign-on).

How new members arrive depends on the access mode you chose: with open sign-up they create their own account and verify it by e-mail; by invitation, you create accounts (or create them from your services' accounts) and each member activates theirs with a link.

## Upgrading

Portalab upgrades its own database: pull the new image, run the migrations, restart.

```bash
docker compose pull                      # with PORTALAB_IMAGE set to the published image
docker compose run --rm migrate
docker compose up -d portalab worker
```

If you build from source, update the repository (`git pull`) and run `docker compose build` instead of `pull`.

- **Back up first.** Save the portal from *Administration › Backups* before a major upgrade (see below).
- **Always run `migrate`.** Until the migrations are applied, `/readyz` reports the portal as not ready. To check whether migrations are pending without applying them: `docker compose run --rm migrate migrate --status`.
- *Administration › Version* shows the running version and revision, the database, and the schema of each module.

## Backups and restore

Portalab saves **the whole portal in one archive encrypted with a passphrase**: members and their accounts, settings, services, content, play, media history and files.

- **Save** from *Administration › Backups*. You choose a passphrase (12 characters at least) and, optionally, the technical history (audit log, metrics, logs) and the images fetched from your services. The portal keeps answering while it saves. Archives are kept in the data volume (`/var/lib/portalab/backups`) and can be downloaded.
- **Restore** on a new installation: the arrival wizard's **Import another Portalab** takes the archive (sent from your browser, or copied into the server's backups folder) and its passphrase. Members keep their accounts and passwords; the services' secrets are encrypted again with the new portal's key. Restart `portalab` and `worker` afterwards.

> **Keep the passphrase safe.** Without it the archive cannot be opened, and nobody can recover it. Copy your archives off the server.

Details, command-line equivalents and the portal reset are in [Running the portal](admin/operations.md#backups-and-restore).

## Where to go next

- [Configuration](configuration.md): environment variables, reverse proxy, going on the internet.
- [Services and integrations](admin/services.md): connect Plex, Jellyfin, Seerr, the *arr apps and more.
- [Members and roles](admin/members-and-roles.md): accounts, access, roles and permissions.
- [Customization](admin/customization.md): themes, visual packs, the members' dashboard.
- [Running the portal](admin/operations.md): backups, monitoring, logs, security.
- Share the [member guides](members/media.md) with your community.

Next: [Configuration](configuration.md) · [Services and integrations](admin/services.md) · [Documentation index](README.md)
