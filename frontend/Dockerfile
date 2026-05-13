# ==============================================================================
# Build Stage: Compile and build the application
# ==============================================================================
FROM node:24-alpine AS base

# Git SHA passed by CI via --build-arg. .git is not in the build context, so
# quasar.config.js can't run `git rev-parse` itself; it reads this env var
# instead. Defaults to "dev" so local `docker build` without --build-arg works.
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

WORKDIR /app

# Copy package files for dependency installation
COPY package.json ./

# Enable Corepack
RUN corepack enable \
 && corepack prepare --activate \
 && npm --version

# ---- Dependencies ----
FROM base AS deps
# Copy package-lock.json for dependency installation
COPY package-lock.json ./

# Install dependencies
# Skip postinstall scripts to avoid running any build steps prematurely
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts --prefer-offline

# ---- Build ----
FROM deps AS build

# Copy source code
COPY . .

# Manually run the quasar prepare script
RUN npx quasar prepare

# Build the application (creates ./dist). GIT_SHA from above gets baked into
# the bundle as APP_VERSION via quasar.config.js build.env.
RUN npm run build

# ==============================================================================
# Production Stage: Serve with unprivileged Nginx
# ==============================================================================
FROM nginxinc/nginx-unprivileged:stable

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Runtime env injection. The base image's stock entrypoint runs every
# /docker-entrypoint.d/*.sh before exec'ing nginx. Numbered 40 to land after
# the base image's own 10–30 init scripts. See docker/entrypoint.sh for what
# it writes and why.
COPY --chmod=755 docker/entrypoint.sh /docker-entrypoint.d/40-inject-env.sh

# Copy built static files. (Source maps are not generated — see
# `sourcemap: false` in quasar.config.js for the reason.)
# --chown=nginx:nginx so the entrypoint script (run as the nginx user) can
# write injectEnv.js into this directory at startup.
COPY --from=build --chown=nginx:nginx /app/dist/spa /usr/share/nginx/html

# Expose non-privileged port
EXPOSE 8080

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ready || exit 1
