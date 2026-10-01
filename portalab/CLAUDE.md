# portalab Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-10-01

## Active Technologies
- Python 3.12 · **Dependencies (new)**: `argon2-cffi`, `Pillow` (avatar validation), plus the 001 baseline (FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2) (015-marketplace)
- PostgreSQL schema `identity` (see `data-model.md`); avatar/export blobs via kernel `core.blobstore` (filesystem baseline) (015-marketplace)

- Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain) + FastAPI, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, Alembic, httpx; React 19, Vite 7 (015-marketplace)

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
- 015-marketplace: Added Python 3.12 · **Dependencies (new)**: `argon2-cffi`, `Pillow` (avatar validation), plus the 001 baseline (FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2)

- 015-marketplace: Added Python 3.12 (backend); TypeScript 5.9 on Node 22 LTS (frontend toolchain) + FastAPI, Pydantic 2, SQLAlchemy 2 (async) + asyncpg, Alembic, httpx; React 19, Vite 7,

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
