# Stage 1: build the Zensical site with build.sh, the same build CI runs
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src/ ./src/
# Every top-level .py and .sh, not a hand-listed set: the next build-time
# script added must not silently break this image.
COPY zensical.toml *.py *.sh ./
RUN sh build.sh

# Stage 2: Serve with nginx (alpine: the debian variant ships ~100 OS
# packages that dominate CVE scans and are unused for serving static files)
FROM nginx/nginx-unprivileged:stable-alpine-slim

# The alpine base lags Alpine's package repo and Trivy blocks the deploy on
# every HIGH it finds there: take every fixed package at build time (#3000).
# Base runs as uid 101 (nginx) — apk needs root.
# GIT_SHA busts the cache for the RUN below: the base digest rarely moves, so
# a cached upgrade layer kept musl 1.2.6-r2 and Trivy blocked dev.
ARG GIT_SHA=dev
USER root
RUN apk upgrade --no-cache
USER 101

# The base default.conf plus the client check of #3196. The geo file
# allows every client: the chart mounts its network list over it.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY client-allowlist.conf /etc/nginx/client-allowlist/geo.conf

# Copy built documentation from builder stage
COPY --from=builder /app/site /usr/share/nginx/html

# Expose nginx port (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
