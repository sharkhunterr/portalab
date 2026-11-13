# Getting started

Install Portalab with Docker Compose, set it up with the arrival wizard, and keep it up to date.

Portalab ships as **one Docker image** with three entrypoints, next to a **PostgreSQL 16** database:

| Entrypoint | What it does |
| --- | --- |
| `serve` (default) | The web interface and the API, on port `8080` |
| `worker` | Background jobs: synchronising services, health probes, notifications, scheduled tasks |
| `migrate` | Creates or upgrades the database schema, then exits |

The Compose file runs `migrate` before it starts `serve` and `worker`, at the first install and at each upgrade.

## Requirements

- A Linux host with **Docker** and the **Docker Compose** plugin (`docker compose`), or **Unraid** with the Docker Compose Manager plugin (see [On Unraid](#on-unraid)).
- Disk space for the database and Portalab's files. Posters, artwork and the trading cards' images fetched from your services can grow to several gigabytes.
- A browser on the **same local network** as the server for the first setup (see [The arrival wizard](#the-arrival-wizard)).

You do not need to install PostgreSQL yourself: the Compose file runs the official `postgres:16-alpine` image.

## Install with Docker Compose

The reference Compose file is [`portalab/deploy/docker-compose.yml`](../portalab/deploy/docker-compose.yml). It needs no preparation: it creates its folders and its secrets on the first start.

### 1. Get the Compose file

```bash
mkdir portalab && cd portalab
curl -fsSLO https://raw.githubusercontent.com/sharkhunterr/portalab/main/portalab/deploy/docker-compose.yml
```

It runs the published image, [`sharkhunterr/portalab:latest`](https://hub.docker.com/r/sharkhunterr/portalab). Each release also has its own tag (for example `1.2.0`): pin one if you prefer to upgrade on your own schedule.

The folder, the port, the image and the reverse-proxy settings can be changed in a `.env` file next to `docker-compose.yml`. [`.env.example`](../portalab/deploy/.env.example) lists them all with their defaults:

```bash
curl -fsSL https://raw.githubusercontent.com/sharkhunterr/portalab/main/portalab/deploy/.env.example -o .env
```

### 2. Start Portalab

```bash
docker compose up -d
```

The services start in this order:

| Service | What it does |
| --- | --- |
| `init` | Creates the folders and generates the secrets, then exits. At each start, it keeps the existing secrets and checks the files' owners. |
| `postgres` | The database |
| `migrate` | Creates or upgrades the database schema, then exits |
| `portalab` | `serve`: the web interface and the API, on port `8080` |
| `worker` | The background jobs |

Everything is kept in **one folder**, `appdata/` next to `docker-compose.yml` (set `PORTALAB_APPDATA` to move it):

| Path | Holds |
| --- | --- |
| `appdata/data/` | Portalab's files (`/var/lib/portalab`): images, cards, visual packs, plugins, backups |
| `appdata/postgres/` | The database |
| `appdata/secrets/postgres/db_password` | The database password, read by PostgreSQL only |
| `appdata/secrets/portalab/database_url` | The PostgreSQL connection URL (`DATABASE_URL_FILE`) |
| `appdata/secrets/portalab/secret_key` | The key that encrypts stored credentials (`SECRET_KEY_FILE`) |

The secrets are random and never pass through the environment: they show neither in `docker inspect` nor in the logs. Each container mounts only its own secrets folder, read-only, and each file can be read only by the user of the container that needs it. To bring your own secrets, write these files before the first start: `init` keeps any file that exists.

> **Keep `secret_key` safe and never change it.** The passwords, API keys and tokens of your connected services are encrypted at rest with a key derived from it. Without the same key, they cannot be read again. If a secret goes missing while the database exists, `init` stops and names the file to restore, instead of generating a new one.

> **Keep `appdata/` on a disk of your own.** A copy of it holds the database and the key that reads it, unencrypted. To keep a copy off the server, use Portalab's own encrypted backups (see [Backups and restore](#backups-and-restore)).

The containers run hardened by default: read-only filesystem, a scratch `/tmp` only, no new privileges, every Linux capability dropped. Portalab writes only to its data folder. `init` runs as root to set the files' owners, without network and with only the rights it needs for that.

To change the published port, the log level or the reverse-proxy settings, see [Configuration](configuration.md).

### 3. Check it is running

```bash
docker compose ps
docker compose logs -f portalab
```

The image has a built-in health check on `/healthz`. You can also run a read-only check of the deployment (who Portalab runs as, whether its code and folders are protected, whether plugins can be confined):

```bash
docker compose run --rm portalab doctor
```

### Run an image built from source

```bash
git clone https://github.com/sharkhunterr/portalab.git && cd portalab
docker build -f portalab/deploy/Dockerfile -t portalab:local .
cd portalab/deploy
echo "PORTALAB_IMAGE=portalab:local" > .env
docker compose up -d
```

## On Unraid

Portalab installs as a stack of the **Docker Compose Manager** plugin.

1. In *Apps*, install **Docker Compose Manager**.
2. In the *Docker* tab, under *Compose*, choose **Add New Stack** and name it `portalab`.
3. On the stack, choose **Edit Stack › Compose File** and paste the content of [`docker-compose.yml`](https://raw.githubusercontent.com/sharkhunterr/portalab/main/portalab/deploy/docker-compose.yml).
4. Choose **Edit Stack › ENV File** and set at least the folder (the other variables are in [`.env.example`](../portalab/deploy/.env.example)):

   ```env
   PORTALAB_APPDATA=/mnt/user/appdata/portalab
   # PORTALAB_PORT=8090    when 8080 is already taken
   ```

5. Choose **Compose Up**. Portalab, its database and its worker appear in the *Docker* tab with their icon, and **WebUI** opens the arrival wizard.

What to know:

- **Always set `PORTALAB_APPDATA`.** The stack's own folder is on the flash drive, which cannot keep the files' owners: `init` stops there and says so.
- **Upgrading** is **Update Stack**: the new image is pulled, and the migrations run before Portalab restarts.
- **When the stack does not start**, Compose Manager only shows `service "init" didn't complete successfully`. The reason is in the logs of `portalab-init` (*Docker* tab, the container's icon, *Logs*).
- **Backups of the appdata share** (the Appdata Backup plugin) hold the database and its key unencrypted: keep them on the server or on a disk of your own, and copy Portalab's encrypted backups off it. Keep the `appdata` share out of SMB (*Shares › appdata › SMB Security Settings › Export: No*).

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

Portalab upgrades its own database: pull the new image and start again.

```bash
docker compose pull
docker compose up -d
```

`up` runs `init` and `migrate` again before it restarts `portalab` and `worker`. If you build from source, update the repository (`git pull`), build the image again (see [Run an image built from source](#run-an-image-built-from-source)) and run `docker compose up -d`.

- **Back up first.** Save the portal from *Administration › Backups* before a major upgrade (see below).
- Until the migrations are applied, `/readyz` reports the portal as not ready. To check whether migrations are pending without applying them: `docker compose run --rm migrate migrate --status`.
- *Administration › Version* shows the running version and build, whether a newer release is out, the portal's security posture, the database, and the schema of each module.

### Coming from the Compose file of Portalab 1.1 or earlier

Until 1.1, the Compose file kept the database and Portalab's files in Docker volumes (`postgres-data`, `portalab-data`), with secrets made by hand in `secrets/`. As long as that `secrets/` folder sits next to the new file and `appdata/` is still empty, `init` refuses to start, so that an empty portal never replaces yours by mistake. Move them once into `appdata/`, from the folder of your current `docker-compose.yml`:

```bash
docker compose down     # stops Portalab, keeps its volumes
docker volume ls --filter name=postgres-data --filter name=portalab-data
docker run --rm -v "$PWD:/d" postgres:16-alpine sh -c 'mkdir -p /d/appdata/secrets/postgres /d/appdata/secrets/portalab && cp /d/secrets/db_password /d/appdata/secrets/postgres/ && cp /d/secrets/database_url /d/secrets/secret_key /d/appdata/secrets/portalab/'
docker run --rm -v deploy_postgres-data:/from -v "$PWD/appdata/postgres:/to" postgres:16-alpine cp -a /from/. /to/
docker run --rm -v deploy_portalab-data:/from -v "$PWD/appdata/data:/to" postgres:16-alpine cp -a /from/. /to/
```

The copies run in a container because `appdata/` may already belong to root. Use the volume names `docker volume ls` shows: the folder's name, then `_postgres-data` and `_portalab-data` (`deploy_…` when the file is in `portalab/deploy`). Then take the new `docker-compose.yml` if you have not already (your `.env` stays valid) and start with `docker compose up -d`: the portal comes back as it was, with the same secrets. Once you have checked it, the old volumes (`docker volume rm …`) and the `secrets/` folder can go.

## Backups and restore

Portalab saves **the whole portal in one archive encrypted with a passphrase**: members and their accounts, settings, services, content, play, media history and files.

- **Save** from *Administration › Backups*. You choose a passphrase (12 characters at least) and, optionally, the technical history (audit log, metrics, logs) and the images fetched from your services. The portal keeps answering while it saves. Archives are kept in the data folder (`appdata/data/backups`, `/var/lib/portalab/backups` in the container) and can be downloaded.
- **Restore** on a new installation: the arrival wizard's **Import another Portalab** takes the archive (sent from your browser, or copied into the server's backups folder) and its passphrase, then lets you untick the parts this portal should not take (the members, the marketplace, the services…; what a part needs comes with it, and the Admin's account always comes). Members keep their accounts and passwords; the services' secrets are encrypted again with the new portal's key. Restart `portalab` and `worker` afterwards.

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
