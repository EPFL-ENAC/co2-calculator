#!/usr/bin/env bash
#
# Runtime env injection for the Quasar SPA.
#
# Why this exists: the same Vite bundle is shipped to dev/stage/prod; per-env
# values (Sentry DSN, environment label, etc.) can't be baked at build time.
# This script runs at container startup (via the nginx-unprivileged base
# image's /docker-entrypoint.d/ hook) and writes APP_*-prefixed env vars into
# /usr/share/nginx/html/injectEnv.js, which the SPA reads as
# window.injectedEnvVariable.
#
# Why a JS file rather than envsubst on index.html: the JS bundle is
# fingerprinted and cached one year (see nginx.conf). injectEnv.js is the only
# no-cache surface, so per-env values must live there or they get pinned to
# the first deploy.
#
# Why /tmp and not /usr/share/nginx/html: in our k8s deployment the pod runs
# with readOnlyRootFilesystem: true (see helm/values.yaml frontend.securityContext)
# so the html dir is read-only at runtime. /tmp is mounted as an emptyDir
# (writable) by the deployment template. nginx.conf has a `location =
# /injectEnv.js` alias that maps the URL to this file.
#
# Why no jq dep: the base nginx-unprivileged image doesn't ship jq, and
# our values are single-line ASCII (DSNs, env names, git SHAs), so a small
# bash escape function is sufficient and keeps the image lean.

set -euo pipefail

OUT_DIR="${OUT_DIR:-/tmp}"
PREFIX="${FRONTEND_ENV_PREFIX:-APP_}"
INJECT_FILE="${OUT_DIR}/injectEnv.js"

# JSON-string escape for value side: backslash, then double-quote. Values are
# assumed single-line ASCII; if you need to inject multi-line or unicode
# values, switch to jq (and apt-get install jq in the Dockerfile).
escape_json() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  printf '%s' "$s"
}

body=""
sep=""
count=0
while IFS='=' read -r key value; do
  case "${key}" in
    "${PREFIX}"*)
      body+="${sep}\"${key}\": \"$(escape_json "${value}")\""
      sep=", "
      count=$((count + 1))
      ;;
  esac
done < <(printenv)

# Atomic write: temp file in the same dir, then mv. Prevents nginx from
# serving a half-written injectEnv.js if this script is killed mid-execution.
tmp=$(mktemp "${OUT_DIR}/injectEnv.js.XXXXXX")
{
  printf '%s\n' \
    "// Generated at container startup by /docker-entrypoint.d/40-inject-env.sh." \
    "// Do not edit; values come from ${PREFIX}*-prefixed env vars at startup." \
    "window.injectedEnvVariable = { ${body} };"
} > "${tmp}"
mv -f "${tmp}" "${INJECT_FILE}"

echo "[entrypoint] wrote ${INJECT_FILE} with ${count} ${PREFIX}* keys"
