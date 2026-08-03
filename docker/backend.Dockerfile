# Multi-stage build so the final image doesn't carry uv, pip caches, or
# build tooling — just a venv and the app code. Build context is backend/
# (see docker-compose.yml: `context: ./backend`, `dockerfile: ../docker/backend.Dockerfile`).

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, in their own layer, so an app-code-only change
# doesn't invalidate the (slow) dependency install on rebuild.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

# Migrations run on every container start, not baked into the image — the
# same code always runs `alembic upgrade head` against whatever database
# it's pointed at, dev or production. `exec` hands off PID 1 to uvicorn so
# it receives SIGTERM directly for a clean shutdown.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
