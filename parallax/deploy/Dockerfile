# The API image: the built web app (web/dist) served by uvicorn from the same origin. Build context: parallax/.
FROM node:22-slim AS web
# git fetches the Arlen ui-kit (gitignored vendor dir) at its pinned commit.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/scripts/ ./scripts/
RUN npm run kit
# Only the sources, never the host's node_modules, vendor or dist.
COPY web/index.html web/vite.config.ts web/tsconfig.json web/svelte.config.js ./
COPY web/src/ ./src/
COPY web/tests/ ./tests/
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
COPY --from=web /app/web/dist web/dist
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
