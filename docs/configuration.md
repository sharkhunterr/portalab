# Configuration

The few settings Portalab reads from its environment at start-up, and how to place it behind a reverse proxy.

Portalab keeps the environment to a minimum: only the **bootstrap** settings it needs before it can reach its database. Everything else (the portal's identity, services, sign-up rules, e-mail, retention, security limits…) is set in the administration and stored in the database, so it travels with your [backups](admin/operations.md#backups-and-restore).

Settings are validated at start-up. A wrong value stops the process with a clear `configuration error: …` message that never contains a secret.

## Bootstrap settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL_FILE` | (required) | Path to a file holding the PostgreSQL URL, e.g. `postgresql://portalab:<password>@postgres:5432/portalab`. `postgres://` and `postgresql://` are accepted; only PostgreSQL is supported. |
| `DATABASE_URL` | (none) | The same URL given inline. Accepted as an alternative, but set **either** `DATABASE_URL` **or** `DATABASE_URL_FILE`, never both. Prefer the file. |
| `SECRET_KEY_FILE` | (required) | Path to a file holding the application key: **at least 32 bytes**. It encrypts the stored credentials of your services (AES-256-GCM). An inline secret key is not accepted. |
| `BIND_HOST` | `0.0.0.0` | Address the server listens on. |
| `BIND_PORT` | `8080` | Port the server listens on (1–65535). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. Logs are structured JSON lines; secrets are redacted. |
| `DATA_DIR` | `/var/lib/portalab` | Absolute path of the data folder: images, cards, visual packs, plugins, backups. Mount a volume here. |
| `TRUSTED_PROXIES` | `127.0.0.1` | Comma-separated addresses or networks of the reverse proxies whose `X-Forwarded-For` header is believed. |
| `HEALTH_NETWORKS` | local networks¹ | Comma-separated addresses or networks allowed to call `/healthz`, `/readyz` and `/metrics`. |
| `SETUP_NETWORKS` | local networks¹ | Comma-separated addresses or networks from which a new (or reset) portal may be set up, or a backup imported into it. |

¹ The built-in default is the machine itself and the private ranges: `127.0.0.0/8`, `::1/128`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`. The reference Compose file narrows `HEALTH_NETWORKS` to the container itself (see below).

Network lists are validated: every entry must be an IP address or a CIDR network.

### Secrets as files

The reference Compose file generates the secrets on the first start (its `init` service) in `appdata/secrets/`, and mounts each container's own folder, read-only, under `/run/secrets/`:

```yaml
environment:
  DATABASE_URL_FILE: /run/secrets/database_url
  SECRET_KEY_FILE: /run/secrets/secret_key
volumes:
  - ${PORTALAB_APPDATA:-./appdata}/secrets/portalab:/run/secrets:ro
```

PostgreSQL reads its own password the same way (`POSTGRES_PASSWORD_FILE`, from `appdata/secrets/postgres/`). To bring your own secrets, write the files before the first start: `init` keeps any file that exists. Never commit the `appdata/` folder. The layout of the folder is in [Getting started](getting-started.md#2-start-portalab).

### Compose variables (`.env`)

The reference [`docker-compose.yml`](../portalab/deploy/docker-compose.yml) reads a few variables from a `.env` file next to it (on Unraid, the stack's ENV file) and passes them to the containers. [`.env.example`](../portalab/deploy/.env.example) lists them with their defaults:

| `.env` variable | Default in Compose | Sets |
| --- | --- | --- |
| `PORTALAB_APPDATA` | `./appdata` | The folder on the host for Portalab's files, the database and the secrets (`/mnt/user/appdata/portalab` on Unraid) |
| `PORTALAB_IMAGE` | `sharkhunterr/portalab:latest` | The image to run: one release (`sharkhunterr/portalab:1.2.0`) or an image built from source (`portalab:local`) |
| `PORTALAB_PORT` | `8080` | The host port published for the web interface |
| `LOG_LEVEL` | `INFO` | `LOG_LEVEL` |
| `PORTALAB_TRUSTED_PROXIES` | `127.0.0.1` | `TRUSTED_PROXIES` |
| `PORTALAB_HEALTH_NETWORKS` | `127.0.0.1/32,::1/128` | `HEALTH_NETWORKS` (the container's own health check asks from itself) |
| `PORTALAB_SETUP_NETWORKS` | the private ranges | `SETUP_NETWORKS` |

Example:

```env
PORTALAB_APPDATA=/mnt/user/appdata/portalab
PORTALAB_PORT=8080
PORTALAB_TRUSTED_PROXIES=172.18.0.0/16
```

### Advanced: pack folders

Two more variables exist for development and unusual layouts. You do not need them with the official image.

| Variable | Default | Meaning |
| --- | --- | --- |
| `PORTALAB_BUILTIN_PACKS_DIR` | `/app/packs/builtin` in the image | Where Portalab's own visual packs are read from |
| `PORTALAB_EXAMPLE_PACKS_DIR` | `/app/packs/examples` in the image | Where the example packs offered by the recommended install are read from |

## Plain HTTP on your LAN

Portalab can be used at `http://<server>:8080` from your local network, without a proxy or a certificate. Browsers refuse `Secure` cookies over plain HTTP, so on such a request (plain HTTP from a private address, never through an untrusted proxy) the session cookies are named `portalab_session` / `portalab_csrf` and go without the `Secure` flag. Over HTTPS, Portalab always uses its `__Host-` cookies and ignores the plain ones.

Plain HTTP sends your password and session in clear on the network: keep it to a network you trust. For anything wider, use a reverse proxy with TLS, as below.

## Behind a reverse proxy

Put Portalab behind a reverse proxy that terminates TLS (Nginx Proxy Manager, Traefik, Caddy…). Three settings decide what answers whom.

### Trusted proxies

Behind a proxy, every request reaches Portalab from the proxy's address. Portalab believes the visitor's real address, written by the proxy in `X-Forwarded-For`, **only from the proxies listed in `TRUSTED_PROXIES`**.

- Set it to the Docker network your proxy reaches Portalab on (for example `172.18.0.0/16`, found with `docker network inspect <network>`), or to the address of the host the proxy runs on.
- **Never use `0.0.0.0/0`**: anyone could then claim any address.
- Without it, every visitor shares the proxy's address: one rate limit for the whole community, and one visitor probing the API can get everyone's sign-in blocked by the intrusion guard. Portalab logs `requests arrive through a reverse proxy that is not trusted` when it detects this.

### Who may reach what

| Setting | Opens | Recommended |
| --- | --- | --- |
| `HEALTH_NETWORKS` | `/healthz` (process alive), `/readyz` (database reachable and migrations current), `/metrics` | Keep it to the container itself (the Compose default), or add your monitoring host. |
| `SETUP_NETWORKS` | The arrival wizard of a portal that is not set up yet (or was reset), and importing a backup into it | Keep the private ranges. Set the portal up from your LAN **before** it is reachable from the internet. |

A request brought by a proxy that is **not** trusted never counts as local, whatever the proxy's own address. This is why an untrusted proxy cannot open the wizard or the health endpoints to the internet.

The Prometheus-format `/metrics` endpoint is also **disabled by default**. Turn it on in *Administration › Configuration* (Observability), where you can also set a bearer token for your scraper.

## Going on the internet

The full checklist for publishing Portalab behind **Nginx Proxy Manager** with **Authentik** single sign-on is in [Putting Portalab on the internet](../portalab/docs/internet-exposure.md). In short:

- Declare the proxy in `TRUSTED_PROXIES`, and check the logs show no untrusted-proxy warning.
- Set the portal up from the LAN before the proxy host exists.
- Forward plain HTTP to the container's port `8080`, with Force SSL, HTTP/2 and HSTS. Live updates use Server-Sent Events, so WebSocket support is not needed.
- Deny `/healthz`, `/readyz` and `/metrics` at the proxy. Optionally keep `/api/v1/admin/` to the LAN only.
- Publish only the proxy on your router, never Portalab's own port.
- For Authentik: the provider's redirect URI is `https://<your portal>/api/v1/auth/oidc/callback`. Bind the application to your members' group, forbid members from changing their own e-mail, and enforce MFA.
- Enable backups and copy them off the machine.

## Everything else is in the administration

Once Portalab runs, you never need to touch the environment again. Every other setting is declared by the module that owns it and changed from the interface:

- **Administration › Configuration** lists every setting of the portal, grouped (General, Members & access, Media & player, Play & shop, Communication, AI assistant, Services, Security & data). For each one it shows its value, its default and where the value comes from, with a search, a preview of each change and an advanced view with the technical keys. Write-only values (such as client secrets) are never shown again once saved.
- Dedicated pages cover the rest: *Site identity*, *Services*, *Roles & permissions*, *Theme studio*, *Modules* and more. See [Running the portal](admin/operations.md) for the full map.

A few examples of what lives in the database rather than the environment:

| Area | Examples |
| --- | --- |
| Members & access | Sign-up mode, password policy, session lengths, single sign-on (issuer, client ID, client secret, button label, account creation) |
| Security & data | Request rate limits, largest request body, outbound allow-list (`security.egress.*`), data retention, audit retention |
| Services | Default sync interval, HTTP timeouts and retries, health probe interval and thresholds, alert rules |
| Observability | Log journal retention, anomaly detectors, escalation to incidents, the `/metrics` endpoint |

Next: [Getting started](getting-started.md) · [Services and integrations](admin/services.md) · [Running the portal](admin/operations.md)
