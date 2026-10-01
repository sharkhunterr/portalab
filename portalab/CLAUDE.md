# portalab Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-10-01

## Active Technologies

- Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain) + FastAPI, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, Alembic, httpx; React 19, Vite 7 (001-architecture)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

Planned (not yet implemented — see specs/001-portal-global-spec/quickstart.md):
cd backend && uv run pytest && uv run ruff check . && uv run lint-imports
cd frontend && npm run lint && npm run typecheck && npm test

## Code Style

Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain): Follow standard conventions

## Recent Changes

- 001-architecture: Added Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain) + FastAPI, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, Alembic, httpx; React 19, Vite 7,

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
