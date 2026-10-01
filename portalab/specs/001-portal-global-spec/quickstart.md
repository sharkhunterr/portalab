# Quickstart — Foundation (target developer & operator experience)

> Describes the **intended** workflow once the work packages in `plan.md` §13 are implemented. Nothing here
> exists yet; commands are the contract the scaffold must satisfy.

## Prerequisites
Docker + Docker Compose, Python 3.12 + `uv`, Node 22 + npm. No local PostgreSQL needed (compose provides it).

## Run (operator)
```bash
cp deploy/.env.example deploy/.env      # set secrets via *_FILE mounts, never commit real values
docker compose -f deploy/docker-compose.yml up -d postgres
docker compose -f deploy/docker-compose.yml run --rm portalab migrate
docker compose -f deploy/docker-compose.yml up -d portalab worker
# open http://localhost:<port>  → first-run wizard establishes the single Admin (spec 020)
```

## Develop
```bash
# backend
cd backend && uv sync && uv run portalab migrate && uv run portalab serve
uv run ruff check . && uv run mypy src && uv run lint-imports && uv run pytest
# frontend
cd frontend && npm ci && npm run dev
npm run lint && npm run typecheck && npm test
```

## Acceptance of the foundation (smoke checks)
1. `/healthz` returns 200; `/readyz` returns 200 only after migrations are current.
2. `uv run lint-imports` passes; adding a forbidden import (module→module internal) makes it fail.
3. A migration test upgrades an empty DB and the previous release's DB.
4. A job enqueued twice with the same `dedup_key` runs once; a crashed worker's job is re-claimed.
5. An unauthenticated request to any non-allow-listed route is refused (default-deny test).
6. Logs contain a correlation id and no secret values.
7. The generated frontend API client matches the OpenAPI schema (drift check).
8. `docker build` produces one image that starts as `serve` and as `worker`.
