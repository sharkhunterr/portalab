# portalab Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-10-01 (consolidated after the pre-implementation audit)

## Active Technologies
- Backend: Python 3.12 · FastAPI · Pydantic 2 · SQLAlchemy 2 (async) + asyncpg · Alembic · httpx · uv · ruff · mypy · import-linter (001)
- Storage: PostgreSQL 16+ only, one schema per module (+ `plugin_<key>` schemas/roles), UUIDv7, `timestamptz` UTC, append-only tables via triggers; extensions `unaccent`, `pg_trgm`, `btree_gist`, optional `pgvector` (001, 008, 014)
- Jobs/events: PostgreSQL jobs + transactional outbox (`SKIP LOCKED`), event store and dedup owned by 007; SSE for live updates (001, 004, 007)
- Frontend: TypeScript 5.9 on Node 22 LTS · React 19 · Vite 7 · TanStack Query · React Router · Radix UI + Tailwind on CSS-variable tokens · react-intl · Recharts · Mermaid (strict) · Biome · Vitest · Playwright + axe (001, 004, 011, 017, 022, 026)
- Domain libraries: `argon2-cffi`, `Pillow` (002); `Babel`, `tzdata` (026); `markdown-it-py`, `nh3`, `diff-match-patch` (011); `aiosmtplib` (010); `jsonschema`, optional `mcp` (018, 019); `packaging` (023)
- Delivery: single Docker image (`serve` / `worker`) + PostgreSQL; GitLab CI stages validate/test/build/publish (001)

## Project Structure

```text
backend/src/portalab/{core, capabilities, modules, connectors, sdk, app}
backend/migrations/<schema>/versions/
backend/tests/{unit,integration,contract,security,migrations}/
frontend/src/{shell, design-system, i18n, features, api}
frontend/tests/{unit,a11y,e2e}/
plugins/{available,installed}/ · examples/plugins/
```

## Commands

Planned (not yet implemented — see specs/001-portal-global-spec/quickstart.md):
cd backend && uv run pytest && uv run ruff check . && uv run mypy src && uv run lint-imports
cd frontend && npm run lint && npm run typecheck && npm test

## Code Style

Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain): follow standard conventions; layers `core ← capabilities ← modules|connectors ← app`; plugins import only `portalab.sdk`.

## Recent Changes
- All 26 specs planned (research, data model, contracts, quickstart, plan, tasks) in roadmap order; audit 2026-10-01 aligned names/ownership (see `decisions/CANONICAL_DECISIONS.md` §7 and `decisions/PLAN_FOLLOWUPS.md`).

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
