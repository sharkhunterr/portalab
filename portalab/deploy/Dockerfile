# Portalab — one image, three entrypoints: `serve` (default), `worker`, `migrate` (research R14).
# Build from the repository root:  docker build -f portalab/deploy/Dockerfile -t portalab .

# ---------------------------------------------------------------- frontend build
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY portalab/frontend/package.json portalab/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY portalab/frontend/ ./
COPY portalab/backend/openapi.json ../backend/openapi.json
COPY portalab/backend/locales ../backend/locales
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
# issue 230: ffmpeg takes the cards' still images from a film's file on the media server
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY portalab/backend/pyproject.toml portalab/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY portalab/backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=frontend /build/frontend/dist ./static
# 028: Portalab's own visual packs (the socle, the universes, the seasons, the HD collections)
COPY portalab/packs/builtin ./packs/builtin
# 253: the example packs, extensions the recommended install sets up when the administrator chooses it
COPY portalab/examples/visual-packs ./packs/examples

RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin portalab \
    && install -d -o 10001 -g 10001 -m 0700 /var/lib/portalab
VOLUME ["/var/lib/portalab"]
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4)"]

ENTRYPOINT ["portalab"]
CMD ["serve"]
