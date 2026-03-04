# ==============================================================================
# Build Stage: Compile and build the application
# ==============================================================================
FROM node:24-alpine AS builder

WORKDIR /app

# Copy package files for dependency installation
COPY package.json package-lock.json ./

# Install dependencies
# Skip postinstall scripts to avoid running any build steps prematurely
RUN npm ci --ignore-scripts

# Copy source code
COPY . .

# Build the application (creates ./dist)
RUN npm run build

# ==============================================================================
# Production Stage: Serve with unprivileged Nginx
# ==============================================================================
FROM nginxinc/nginx-unprivileged:stable

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built static files from build stage
COPY --from=builder /app/dist/spa /usr/share/nginx/html

# Ensure writable temp paths for any runtime needs
# (important for OpenShift random UID compatibility)
RUN mkdir -p /tmp/nginx \
    && chmod -R 777 /tmp/nginx

# Expose non-privileged port
EXPOSE 8080

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/health || exit 1
