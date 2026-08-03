# Build context is discord_bot/ (see docker-compose.yml). No exposed port
# and no HEALTHCHECK — this process only makes outbound connections
# (Discord's gateway, the backend API), nothing to probe locally.

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

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

CMD ["python", "main.py"]
