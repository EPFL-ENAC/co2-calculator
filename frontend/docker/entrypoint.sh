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
# One folder is one institution, mounted at INSTITUTION_DIR: theme.conf
# (required), values.env (optional, APP_<NAME>=value lines) and the assets.
# A variable of the environment wins over values.env, so a deployment can
# give every value through the environment and have no values.env.
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
# file (see build/institution.mjs), so the checks and the two parsers below
# have one implementation.
#
# The awk programs sit inside single quotes: do not write an apostrophe in
# them, not even in a comment.

# No pipefail: POSIX only added it in the 2024 spec and older /bin/sh
# implementations lack it. No pipeline below has a left-hand command that can
# fail.
set -eu

OUT_DIR="${OUT_DIR:-/tmp}"
INSTITUTION_DIR="${INSTITUTION_DIR:-/institution}"
# Optional: without it, every value comes from the environment.
ENV_FILE=""
if [ -f "${INSTITUTION_DIR}/values.env" ]; then
  ENV_FILE="${INSTITUTION_DIR}/values.env"
fi
DEFAULT_DIR="${INSTITUTION_DEFAULT_DIR:-/usr/local/share/institution/default}"

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
font-regular.woff2
font-medium.woff2
font-bold.woff2
"

fail() {
  echo "[entrypoint] $1" >&2
  exit 1
}

# ------------------------------------------------------------------------------
# 1. Values: injectEnv.js
# ------------------------------------------------------------------------------

# Atomic write: temp file in the same dir, then mv. nginx never serves a
# half-written file. awk reads values.env first, when the folder has one, then
# the environment on stdin ("-"), so the environment wins.
tmp=$(mktemp "${OUT_DIR}/injectEnv.js.XXXXXX")
if ! printenv | awk -v env_file="${ENV_FILE}" '
  function fail(message) {
    print "[entrypoint] " message > "/dev/stderr"
    failed = 1
  }
  function empty(key) { return !(key in values) || values[key] == "" }

  # values.env: APP_<NAME>=value lines, "#" comments, values are literal.
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
    value = substr($0, eq + 1)
    from_file = (env_file != "" && FILENAME == env_file)
    if (!from_file) {
      # printenv gives lines, and a value can hold a line break: the true
      # value is in ENVIRON. A line with a name that ENVIRON does not have
      # is the rest of such a value, not a variable.
      if (!(key in ENVIRON)) next
      if (key !~ /^APP_[A-Z0-9_]+$/) {
        fail(key ": a name is APP_ and then capital letters, digits or _")
        next
      }
      value = ENVIRON[key]
      # Not silent: a deployment that sets both must see which one it gets.
      if ((key in values) && values[key] != value) {
        print "[entrypoint] " key ": the environment replaces values.env" > "/dev/stderr"
      }
    }
    if (index(value, "\n") || index(value, "\r")) {
      fail(key ": a value cannot hold a line break")
      next
    }
    if (!(key in values)) order[++count] = key
    values[key] = value
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

# The folder is flat: a ConfigMap key cannot hold a "/", so one folder mounts
# from a ConfigMap, a volume or a local path alike. Names that start with "."
# are skipped: a Kubernetes ConfigMap mount adds ..data and others.
subfolders=$(cd "${INSTITUTION_DIR}" && find -L . -mindepth 1 -name '.*' -prune \
  -o -type d -print | sed 's|^\./||' | while read -r dir; do printf ' %s' "${dir}"; done)
if [ -n "${subfolders}" ]; then
  fail "subfolders in ${INSTITUTION_DIR}:${subfolders}. The folder is flat, it must hold files only."
fi

# A file the app does not read is a typo of a file it reads. A font-* file
# that is not a .woff2 is allowed and not copied: a free font must keep its
# license next to it (see institution-default/font-README.md).
# values.env is known but not an asset: the loop below copies only ASSET_FILES.
known=" theme.conf values.env $(echo ${ASSET_FILES}) "
print_unknown() {
  while read -r file; do
    case "${known}" in
      *" ${file} "*) continue ;;
    esac
    case "${file}" in
      font-*.woff2) printf ' %s' "${file}" ;;
      font-*) ;;
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

# Input: one "name: value" line per value, "#" starts a comment line.
# Output: ":root { --theme-<name>: <value>; ... }" and one @font-face rule per
# font weight. The names in the three lists are the whole contract:
# institution-default/theme.conf.example documents each one, and
# scripts/check-theme-keys.mjs fails `make type-check` when the colors and
# lengths lists and the --theme-* names of the SCSS differ.
#
# A value is pasted into CSS, so each kind accepts one shape only and
# everything else is refused: a hex color, a length, a font URL.
tmp=$(mktemp "${OUT_DIR}/theme.css.XXXXXX")
if ! awk '
  BEGIN {
    split("accent accent-hover accent-light accent-lighter " \
          "text text-muted surface border link highlight " \
          "validated validated-light success warning error", colors, " ")
    split("radius radius-lg", lengths, " ")
    # Font names are not CSS properties: @font-face cannot read var().
    split("font-regular font-medium font-bold", fonts, " ")
    for (i in colors) kind[colors[i]] = "color"
    for (i in lengths) kind[lengths[i]] = "length"
    weight["font-regular"] = 400
    weight["font-medium"] = 500
    weight["font-bold"] = 700
    for (i in fonts) {
      kind[fonts[i]] = "font"
      # Without a URL, the font is the file of the same name in the assets.
      font[fonts[i]] = "/institution/" fonts[i] ".woff2"
    }
  }

  function fail(message) {
    printf "[entrypoint] %s line %d: %s\n", FILENAME, FNR, message > "/dev/stderr"
    failed = 1
  }
  # No {n,m} interval: not every awk has it. Class test, then the length.
  function is_color(value,    digits) {
    digits = length(value) - 1
    return value ~ /^#[0-9a-fA-F]+$/ && \
      (digits == 3 || digits == 4 || digits == 6 || digits == 8)
  }
  function is_length(value) {
    return value == "0" || value ~ /^[0-9]+(\.[0-9]+)?(px|rem|em|%)$/
  }
  # https://host/... or /path, never //host. Only the characters of a plain
  # URL, so nothing can end the url("...") string.
  function is_font_url(value) {
    return value ~ /^(https:\/\/|\/)[A-Za-z0-9._~%\/?=&+:-]+$/ && \
      value !~ /^\/\//
  }

  # \r: a theme.conf saved with Windows line endings.
  /^[ \t\r]*(#|$)/ { next }

  {
    colon = index($0, ":")
    if (colon == 0) { fail("expected \"name: value\""); next }
    name = substr($0, 1, colon - 1)
    value = substr($0, colon + 1)
    gsub(/^[ \t]+|[ \t\r]+$/, "", name)
    gsub(/^[ \t]+|[ \t\r]+$/, "", value)
    if (!(name in kind)) { fail("unknown name \"" name "\""); next }
    if (name in seen) { fail("\"" name "\" is set twice"); next }
    seen[name] = 1
    if (kind[name] == "color" && !is_color(value)) {
      fail("\"" name "\" must be a hex color, for example #0050a0"); next
    }
    if (kind[name] == "length" && !is_length(value)) {
      fail("\"" name "\" must be a length in px, rem, em or %"); next
    }
    if (kind[name] == "font") {
      if (!is_font_url(value)) {
        fail("\"" name "\" must be an https:// URL or a path that starts with /")
        next
      }
      font[name] = value
      next
    }
    order[++count] = name
    values[name] = value
  }

  END {
    if (!("accent" in seen)) {
      printf "[entrypoint] %s: \"accent\" is required\n", FILENAME > "/dev/stderr"
      failed = 1
    }
    if (failed) exit 1
    print ":root {"
    for (i = 1; i <= count; i++) printf "  --theme-%s: %s;\n", order[i], values[order[i]]
    print "}"
    for (i = 1; i <= 3; i++) {
      name = fonts[i]
      printf "@font-face {\n  font-family: InstitutionFont;\n  src: url(\"%s\") format(\"woff2\");\n  font-weight: %d;\n  font-style: normal;\n  font-display: swap;\n}\n", font[name], weight[name]
    }
  }' "${INSTITUTION_DIR}/theme.conf" > "${tmp}"; then
  rm -f "${tmp}"
  fail "invalid theme file ${INSTITUTION_DIR}/theme.conf"
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/theme.css"

echo "[entrypoint] wrote injectEnv.js, institution/ and theme.css in ${OUT_DIR}"
