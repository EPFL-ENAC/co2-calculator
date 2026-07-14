#!/bin/sh
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
# Why POSIX sh + awk, not bash or jq: the alpine-slim base ships neither, and
# our values are single-line ASCII (DSNs, env names, git SHAs), so awk's
# gsub-based JSON escaping is sufficient and keeps the image lean.

# No pipefail: POSIX only added it in the 2024 spec and older /bin/sh
# implementations lack it. Re-add (as `set -o pipefail`) if a pipeline gains a
# left-hand command that can actually fail — today both start with printenv.
set -eu

OUT_DIR="${OUT_DIR:-/tmp}"
PREFIX="${FRONTEND_ENV_PREFIX:-APP_}"
INJECT_FILE="${OUT_DIR}/injectEnv.js"

count=$(printenv | grep -c "^${PREFIX}") || count=0

# Atomic write: temp file in the same dir, then mv. Prevents nginx from
# serving a half-written injectEnv.js if this script is killed mid-execution.
tmp=$(mktemp "${OUT_DIR}/injectEnv.js.XXXXXX")
{
  printf '%s\n' \
    "// Generated at container startup by /docker-entrypoint.d/40-inject-env.sh." \
    "// Do not edit; values come from ${PREFIX}*-prefixed env vars at startup."
  printenv | awk -v prefix="${PREFIX}" '
    index($0, prefix) == 1 {
      eq = index($0, "=")
      key = substr($0, 1, eq - 1)
      value = substr($0, eq + 1)
      gsub(/\\/, "\\\\&", value)
      gsub(/"/, "\\\\&", value)
      pairs = pairs sep "\"" key "\": \"" value "\""
      sep = ", "
    }
    END { print "window.injectedEnvVariable = { " pairs " };" }'
} > "${tmp}"
mv -f "${tmp}" "${INJECT_FILE}"

echo "[entrypoint] wrote ${INJECT_FILE} with ${count} ${PREFIX}* keys"
