# Putting Portalab on the internet

Portalab runs as its Docker image (`deploy/docker-compose.yml`) behind a reverse proxy that terminates TLS —
Nginx Proxy Manager (NPM) here — and optionally Authentik for the single sign-on. This page lists what has
to be set for that, and why.

## 1. Tell Portalab who its proxy is (#273)

Behind a proxy, every request reaches Portalab from the proxy's address. Portalab believes the visitor's
address the proxy writes in `X-Forwarded-For` **only from the proxies it is told about**:

```env
# .env next to docker-compose.yml
PORTALAB_TRUSTED_PROXIES=172.18.0.0/16   # the Docker network NPM reaches Portalab on (or NPM's host address)
```

- Find the right value with `docker network inspect <network>` (NPM and Portalab on one network), or use the
  address of the host NPM runs on when Portalab is published on a port.
- Never `0.0.0.0/0`: anyone could then claim any address.
- Without it, every visitor has the proxy's address: one rate limit for the whole community, and one
  visitor probing the API blocks everyone's sign-in for a while. Portalab logs
  `requests arrive through a reverse proxy that is not trusted` when it sees that.

## 2. What answers whom

| Setting (`.env`) | Default in compose | What it opens |
| --- | --- | --- |
| `PORTALAB_HEALTH_NETWORKS` | `127.0.0.1/32,::1/128` | `/healthz`, `/readyz`, `/metrics` (the container's own health check asks from itself) |
| `PORTALAB_SETUP_NETWORKS` | the private ranges | setting a new (or reset) portal up, bringing a backup into it (#275) |

A portal that is not set up yet answers its arrival wizard to the local networks only: set it up (or import
its backup) from the LAN, then open it to the internet. A request a non-trusted proxy brings never counts as
local, whatever the proxy's own address.

## 3. Nginx Proxy Manager

- Proxy host → scheme `http`, forward to the Portalab container on port `8080`; **Force SSL**, **HTTP/2**,
  **HSTS** on. Websockets support is not needed (live updates are Server-Sent Events; Portalab already sends
  `X-Accel-Buffering: no`).
- NPM forwards `X-Forwarded-For` and `X-Forwarded-Proto` by default — keep it so (the single sign-on builds
  its way back from them).
- Custom locations, or in *Advanced*:

  ```nginx
  location ~ ^/(healthz|readyz|metrics)$ { deny all; }
  ```

- Optional: `/api/v1/admin/` only from the LAN (`allow 192.168.1.0/24; deny all;` in a custom location) —
  the administrators then manage the portal from home only.
- Do not publish the container's port on the router: only NPM is reachable from outside.

## 4. Authentik (single sign-on)

- Accounts are linked by the server: a provider account signs in as the member it is linked to, else the
  member of the same e-mail, else a new member (unless *Create accounts* is off).
- The Admin's account is linked by e-mail **only when Authentik vouches for the e-mail**
  (`email_verified: true` in the `email` scope mapping); otherwise the Admin keeps signing in with their
  password.
- In Authentik: bind the application to the group of the community's members; **forbid members from
  changing their own e-mail** (the user settings flow); enforce MFA on that group.
- A sign-on is finished only in the browser that started it (a short cookie): nobody can sign a victim in
  as themselves with a link.

## 5. Checklist

- [ ] `PORTALAB_TRUSTED_PROXIES` set; no warning about an untrusted proxy in the logs
- [ ] portal set up from the LAN before the proxy host exists
- [ ] `/healthz` from outside answers 401 (or NPM's 403)
- [ ] dependencies up to date (`uv lock --upgrade`, `npm audit --omit=dev`)
- [ ] backups enabled and copied off the machine
