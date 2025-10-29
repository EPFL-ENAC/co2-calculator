# =========================
# 1️⃣ Builder Stage
# =========================
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app

# Copy dependency manifests first (for better Docker cache)
COPY pyproject.toml uv.lock ./

# Sync deps into a local venv (no dev deps, no cache)
RUN uv sync --frozen --no-dev --no-cache --compile-bytecode

# Copy source code
COPY . .

# =========================
# 2️⃣ Runtime Stage
# =========================
FROM alpine:3.20 AS runtime

# Add system deps required to run Python (no compilers)
RUN apk add --no-cache python3 libstdc++ && \
    adduser -D appuser

WORKDIR /app
USER appuser

# Copy Python venv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy only app code (keep it lean)
COPY --from=builder /app/app /app/app

EXPOSE 8000

# Entrypoint: run app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
