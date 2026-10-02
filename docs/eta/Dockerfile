# Exploratory (#3002): the docs site built with vite-ssr-i18n-basic + Eta.
# The context is docs/, since pages come from src/ and the nav from
# zensical.toml:  docker build -f docs/eta/Dockerfile docs/
FROM node:26.5.0-alpine AS builder
WORKDIR /app/eta
COPY eta/package.json eta/package-lock.json eta/.npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY zensical.toml /app/
COPY src/ /app/src/
COPY eta/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine-slim
# Same as docs/Dockerfile: Trivy blocks on base-image CVEs Alpine has fixed.
USER root
RUN apk upgrade --no-cache
USER 101
COPY --from=builder /app/eta/dist /usr/share/nginx/html
EXPOSE 8080
