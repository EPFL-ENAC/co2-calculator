# =========================
# 1- Builder Stage
# =========================
# Alpine (musl) on both stages: the runtime is alpine to shed the Debian base
# packages (perl, util-linux, ...) that dominate CVE scans, and the venv must
# be built on the same libc it runs on.
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app

# Install git for dependencies from git repositories
RUN apk add --no-cache git

# Copy dependency manifests first
COPY pyproject.toml uv.lock ./

# Install dependencies into a Linux-native venv, using BuildKit cache to avoid re-downloading
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --compile-bytecode

# Install OpenTelemetry instrumentation packages
# https://opentelemetry.io/docs/zero-code/python/troubleshooting/#bootstrap-using-uv
ENV PATH="/app/.venv/bin:$PATH"
# Call the venv binary directly: `uv run` would implicitly sync the default
# dependency groups (including dev), re-adding pytest/mypy/locust to the
# runtime venv and making bootstrap instrument those packages too.
RUN opentelemetry-bootstrap -a requirements | uv pip install --requirement -

# Copy application source and config only
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./

# =========================
# 2-  Runtime Stage
# =========================
FROM python:3.14-alpine AS runtime

WORKDIR /app

RUN addgroup -g 1001 appgroup && \
  adduser -D -H -s /sbin/nologin -u 1001 -G appgroup appuser && \
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
