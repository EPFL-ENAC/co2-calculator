# =========================
# 1- Builder Stage
# =========================
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS builder

WORKDIR /app

# Install git for dependencies from git repositories
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first
COPY pyproject.toml uv.lock ./

# Install dependencies into a Linux-native venv, using BuildKit cache to avoid re-downloading
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --compile-bytecode

# Install OpenTelemetry instrumentation packages
# https://opentelemetry.io/docs/zero-code/python/troubleshooting/#bootstrap-using-uv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv run opentelemetry-bootstrap -a requirements | uv pip install --requirement -

# Copy application source and config only
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./

# =========================
# 2-  Runtime Stage
# =========================
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN groupadd -g 1001 appgroup && \
  useradd -M -s /sbin/nologin -u 1001 -g appgroup appuser && \
  chown -R appuser:appgroup /app

USER appuser

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONUNBUFFERED=1 \
  PYTHONFAULTHANDLER=1 \
  HOST=0.0.0.0 \
  PORT=8000 \
  WORKERS=1 \
  OTEL_PYTHON_FORK_SAFE=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8000') + '/ready')" || exit 1

# Use environment variables in CMD
CMD ["sh", "-c", "exec opentelemetry-instrument uvicorn app.main:app --host $HOST --port $PORT --workers $WORKERS"]
