FROM ghcr.io/astral-sh/uv:0.11.8 AS uv

FROM node:22.12.0-bookworm-slim AS frontend
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY frontend ./frontend
COPY vite.config.ts ./
RUN npm run build

FROM python:3.12.13-slim-bookworm AS runtime
WORKDIR /app

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-default-groups

COPY backend ./backend
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    CORE_PROFILE=HOSTED \
    CORE_BIND_HOST=0.0.0.0 \
    CORE_STATE_ROOT=/data/core \
    CORE_RAILWAY_VOLUME_PATH=/data \
    CORE_SPA_DIST_DIR=/app/frontend/dist \
    CORE_API_PROXY_PREFIX=/api \
    CORE_WEB_WORKER_COUNT=1 \
    CORE_SQLITE_WRITER_COUNT=1 \
    CORE_COMPUTE_SUBPROCESS_COUNT=1 \
    CORE_GEMINI_ENABLED=false

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready')"

CMD ["sh", "-c", "exec uv run --locked --no-sync uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
