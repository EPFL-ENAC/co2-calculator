# =========================
# 1️⃣ Builder Stage
# =========================
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app

# Install git for dependencies from git repositories
RUN apk add --no-cache git

# Copy dependency manifests first
COPY pyproject.toml uv.lock ./

# Install dependencies into a Linux-native venv
RUN uv sync --frozen --no-dev --no-cache --compile-bytecode

# Install OpenTelemetry dependencies
# https://opentelemetry.io/docs/zero-code/python/troubleshooting/#bootstrap-using-uv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv run opentelemetry-bootstrap -a requirements | uv pip install --requirement -

# Copy application source and config only
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./

# =========================
# 2️⃣ Runtime Stage
# =========================
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS runtime

WORKDIR /app
RUN addgroup -g 1001 appgroup && \
    adduser -D -H -u 1001 -G appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini


ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
