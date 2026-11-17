#!/bin/sh
#
# Startup of the frontend container: values, institution assets and theme.
#
# Why this exists: one image serves every environment and every institution
# (#3244), so nothing of a deployment is in the bundle. This script runs at
# container startup, through the /docker-entrypoint.d/ hook of the
# nginx-unprivileged base image, and writes three things into OUT_DIR:
#
#   injectEnv.js   the APP_* environment variables, read by the SPA as
#                  window.injectedEnvVariable
#   institution/   logo, browser icons, login illustration and fonts: the
#                  defaults of the image, then the files of the mounted folder
#   theme.css      colors, corner radii and fonts, from theme.conf of the
#                  mounted folder
#
# Any error exits 1, and the nginx entrypoint then stops the container: a
# rollout with a wrong value keeps the old pods instead of serving a broken
# app.
#
# Every APP_* value is PUBLIC: injectEnv.js goes to every browser, without a
# login. Never put a secret in an APP_* variable. A key whose name looks like
# a secret stops the startup.
#
# Why a JS file and not envsubst on index.html: the JS bundle is fingerprinted
# and cached one year (see nginx.conf). injectEnv.js is a no-cache surface, so
# per-deployment values must live there or they get pinned to the first deploy.
#
# Why OUT_DIR is /tmp: the pod runs with readOnlyRootFilesystem (see
# helm/values.yaml frontend.securityContext), and /tmp is a writable emptyDir.
# nginx.conf maps /injectEnv.js, /theme.css and /institution/ to it.
#
# Why POSIX sh and awk, not node, python, bash or jq: the alpine-slim base
# ships none of them. The dev server, the tests and Storybook run this same
# file (see build/institution.mjs), so the checks and the parsers have one
# implementation. Those runs set INSTITUTION_ENV_FILE, a file of
# APP_<NAME>=value lines that stands for the pod environment. A variable of
# the shell wins over the file.
#
# The awk program sits inside single quotes: do not write an apostrophe in
# it, not even in a comment.

# No pipefail: POSIX only added it in the 2024 spec and older /bin/sh
# implementations lack it. No pipeline below has a left-hand command that can
# fail.
set -eu

OUT_DIR="${OUT_DIR:-/tmp}"
ENV_FILE="${INSTITUTION_ENV_FILE:-}"
INSTITUTION_DIR="${INSTITUTION_DIR:-/institution}"
DEFAULT_DIR="${INSTITUTION_DEFAULT_DIR:-/usr/local/share/institution/default}"
THEME_AWK="${THEME_AWK:-$(dirname "$0")/theme.awk}"

# Keep in sync with the references in index.html and the logo components.
# Each one has a default in DEFAULT_DIR.
ASSET_FILES="
logo.svg
login-illustration.svg
favicon.ico
favicon-16x16.png
favicon-32x32.png
favicon-96x96.png
favicon-128x128.png
fonts/regular.woff2
fonts/medium.woff2
fonts/bold.woff2
"

fail() {
  echo "[entrypoint] $1" >&2
  exit 1
}

# ------------------------------------------------------------------------------
# 1. Values: injectEnv.js
# ------------------------------------------------------------------------------

if [ -n "${ENV_FILE}" ] && [ ! -f "${ENV_FILE}" ]; then
  fail "INSTITUTION_ENV_FILE does not exist: ${ENV_FILE}"
fi

# Atomic write: temp file in the same dir, then mv. nginx never serves a
# half-written file. awk reads the env file first, when one is set, then the
# environment on stdin ("-"), so the environment wins.
tmp=$(mktemp "${OUT_DIR}/injectEnv.js.XXXXXX")
if ! printenv | awk -v env_file="${ENV_FILE}" '
  function fail(message) {
    print "[entrypoint] " message > "/dev/stderr"
    failed = 1
  }
  function empty(key) { return !(key in values) || values[key] == "" }

  # The env file: APP_<NAME>=value lines, "#" comments, values are literal.
  env_file != "" && FILENAME == env_file {
    sub(/\r$/, "")
    if ($0 ~ /^[ \t]*(#|$)/) next
    if ($0 !~ /^APP_[A-Z0-9_]+=/) {
      fail(FILENAME " line " FNR ": expected APP_<NAME>=value")
      next
    }
  }
  # The environment holds much more than our values.
  index($0, "APP_") != 1 { next }
  {
    eq = index($0, "=")
    key = substr($0, 1, eq - 1)
    if (!(key in values)) order[++count] = key
    values[key] = substr($0, eq + 1)
  }

  END {
    for (i = 1; i <= count; i++) {
      if (order[i] ~ /SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE/) {
        fail(order[i] ": every APP_* value is public, a secret cannot be one")
      }
    }
    # The texts and the links of the app use these: no default exists.
    split("APP_INSTITUTION_NAME APP_INSTITUTION_NAME_FR_DE " \
          "APP_INSTITUTION_NAME_FR_A APP_INSTITUTIONAL_ID_LABEL " \
          "APP_CONTACT_EMAIL APP_USER_DOC_URL APP_BACKOFFICE_DOC_URL " \
          "APP_STRATEGY_URL_EN APP_STRATEGY_URL_FR", required, " ")
    for (i = 1; i in required; i++) {
      if (empty(required[i])) fail(required[i] " is required and empty")
    }
    # A switch that is on makes its value required.
    if (!empty("APP_MATOMO_SITE_ID") && empty("APP_MATOMO_URL")) {
      fail("APP_MATOMO_URL is required with APP_MATOMO_SITE_ID")
    }
    # Same test as isDemoMode in src/utils/demoMode.ts.
    demo = empty("APP_DEMO_MODE") ? "" : tolower(values["APP_DEMO_MODE"])
    gsub(/^[ \t]+|[ \t]+$/, "", demo)
    if (demo == "true" && empty("APP_PRODUCTION_URL")) {
      fail("APP_PRODUCTION_URL is required with APP_DEMO_MODE=true")
    }
    # The texts add a page path after these URLs.
    split("APP_USER_DOC_URL APP_BACKOFFICE_DOC_URL", slash, " ")
    for (i = 1; i in slash; i++) {
      if (!empty(slash[i]) && values[slash[i]] !~ /\/$/) {
        fail(slash[i] " must end with /")
      }
    }
    if (failed) exit 1

    print "// Generated at container startup by docker/entrypoint.sh."
    print "// Do not edit: the values are the APP_* environment variables."
    for (i = 1; i <= count; i++) {
      value = values[order[i]]
      gsub(/\\/, "\\\\&", value)
      gsub(/"/, "\\\\&", value)
      pairs = pairs sep "\"" order[i] "\": \"" value "\""
      sep = ", "
    }
    print "window.injectedEnvVariable = { " pairs " };"
  }' ${ENV_FILE:+"${ENV_FILE}"} - > "${tmp}"; then
  rm -f "${tmp}"
  fail "invalid APP_* values, see the lines above"
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/injectEnv.js"

# ------------------------------------------------------------------------------
# 2. Assets: institution/
# ------------------------------------------------------------------------------

if [ ! -s "${INSTITUTION_DIR}/theme.conf" ]; then
  fail "missing or empty: ${INSTITUTION_DIR}/theme.conf. It sets the accent color."
fi

# A file the app does not read is a typo of a file it reads. Names that start
# with "." are skipped: a Kubernetes ConfigMap mount adds ..data and others.
# A file of fonts/ that is not a .woff2 is allowed: a free font must keep its
# license next to it (see institution-default/fonts/README.md).
known=" theme.conf $(echo ${ASSET_FILES}) "
print_unknown() {
  while read -r file; do
    case "${known}" in
      *" ${file} "*) continue ;;
    esac
    case "${file}" in
      fonts/*.woff2) printf ' %s' "${file}" ;;
      fonts/*) ;;
      *) printf ' %s' "${file}" ;;
    esac
  done
}
unknown=$(cd "${INSTITUTION_DIR}" && find -L . -mindepth 1 -name '.*' -prune \
  -o -type f -print | sed 's|^\./||' | print_unknown)
if [ -n "${unknown}" ]; then
  fail "unknown files in ${INSTITUTION_DIR}:${unknown}. The names are in the defaults folder of the image."
fi

# Build the folder next to the old one, then swap: nginx and the dev server
# never serve a half-copied folder. The log names the source of each file, so
# a deployment that forgets an override shows it.
tmp_dir=$(mktemp -d "${OUT_DIR}/institution.XXXXXX")
mkdir "${tmp_dir}/fonts"
for file in ${ASSET_FILES}; do
  source="${DEFAULT_DIR}"
  if [ -e "${INSTITUTION_DIR}/${file}" ]; then
    if [ ! -s "${INSTITUTION_DIR}/${file}" ]; then
      rm -rf "${tmp_dir}"
      fail "empty file: ${INSTITUTION_DIR}/${file}"
    fi
    source="${INSTITUTION_DIR}"
  fi
  cp "${source}/${file}" "${tmp_dir}/${file}"
  echo "[entrypoint] ${file}: from ${source}"
done
chmod -R a+rX "${tmp_dir}"
rm -rf "${OUT_DIR}/institution"
mv "${tmp_dir}" "${OUT_DIR}/institution"

# ------------------------------------------------------------------------------
# 3. Theme: theme.css
# ------------------------------------------------------------------------------

# docker/theme.awk reads theme.conf and prints the CSS.
tmp=$(mktemp "${OUT_DIR}/theme.css.XXXXXX")
if ! awk -f "${THEME_AWK}" "${INSTITUTION_DIR}/theme.conf" > "${tmp}"; then
  rm -f "${tmp}"
  fail "invalid theme file ${INSTITUTION_DIR}/theme.conf"
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/theme.css"

echo "[entrypoint] wrote injectEnv.js, institution/ and theme.css in ${OUT_DIR}"
