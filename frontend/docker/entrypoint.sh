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
# When INDEX_HTML names the built page (the container, `vite preview`), the
# values and the theme go into a copy of it, OUT_DIR/index.html, in place of
# the two tags that load them, and the two files are removed. The first
# response then carries them: two requests less, one of them render-blocking.
# A run without a built page (`quasar dev`, component tests, Storybook) sets
# INDEX_HTML empty and keeps the two files.
#
# Any error exits 1, and the nginx entrypoint then stops the container: a
# rollout with a wrong value keeps the old pods instead of serving a broken
# app.
#
# Every APP_* value is PUBLIC: the page goes to every browser, without a
# login. Never put a secret in an APP_* variable. A key whose name looks like
# a secret stops the startup.
#
# Why the page and not the bundle: the JS bundle is fingerprinted and cached
# one year (see nginx.conf). index.html is a no-cache surface, so
# per-deployment values must live there or they get pinned to the first deploy.
#
# Why OUT_DIR is /tmp: the pod runs with readOnlyRootFilesystem (see
# helm/values.yaml frontend.securityContext), and /tmp is a writable emptyDir.
# nginx.conf maps /index.html and /institution/ to it.
#
# Why POSIX sh and awk, not node, python, bash or jq: the alpine-slim base
# ships none of them. The dev server, the tests and Storybook run this same
# file (see build/institution.mjs), so the checks and the two parsers below
# have one implementation. Those runs set INSTITUTION_ENV_FILE, a file of
# APP_<NAME>=value lines that stands for the pod environment. A variable of
# the shell wins over the file.
#
# The awk programs sit inside single quotes: do not write an apostrophe in
# them, not even in a comment.

# No pipefail: POSIX only added it in the 2024 spec and older /bin/sh
# implementations lack it. No pipeline below has a left-hand command that can
# fail.
set -eu

OUT_DIR="${OUT_DIR:-/tmp}"
ENV_FILE="${INSTITUTION_ENV_FILE:-}"
INSTITUTION_DIR="${INSTITUTION_DIR:-/institution}"
DEFAULT_DIR="${INSTITUTION_DEFAULT_DIR:-/usr/local/share/institution/default}"
# "-", not ":-": an empty value means a run without a built page, see above.
INDEX_HTML="${INDEX_HTML-/usr/share/nginx/html/index.html}"

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

    for (i = 1; i <= count; i++) {
      value = values[order[i]]
      gsub(/\\/, "\\\\&", value)
      gsub(/"/, "\\\\&", value)
      pairs = pairs sep "\"" order[i] "\": \"" value "\""
      sep = ", "
    }
    # This line goes into a <script> element of the page. "<" as a JS escape:
    # no key or value can then close the element or open an HTML comment.
    # split and join, not gsub: awks differ on a backslash in a replacement.
    parts = split(pairs, piece, "<")
    pairs = piece[1]
    for (i = 2; i <= parts; i++) pairs = pairs "\\u003c" piece[i]
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

# Input: one "name: value" line per value, "#" starts a comment line.
# Output: ":root { --theme-<name>: <value>; ... }" and one @font-face rule per
# font weight. The names in the three lists are the whole contract:
# institution-default/theme.conf.example documents each one, and
# scripts/check-theme-keys.mjs fails `make type-check` when the colors and
# lengths lists and the --theme-* names of the SCSS differ.
#
# A value is pasted into CSS, so each kind accepts one shape only and
# everything else is refused: a hex color, a length, a font URL. No shape
# accepts "<", so the CSS cannot close the <style> element of the page.
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
      # Without a URL, the font comes from the fonts/ folder of the assets.
      font[fonts[i]] = "/institution/fonts/" substr(fonts[i], 6) ".woff2"
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

if [ -z "${INDEX_HTML}" ]; then
  echo "[entrypoint] wrote injectEnv.js, institution/ and theme.css in ${OUT_DIR}"
  exit 0
fi

# ------------------------------------------------------------------------------
# 4. Page: index.html with the values and the theme inside
# ------------------------------------------------------------------------------

# Why: as files, the browser finds the values and the theme only after it
# reads the page, and theme.css blocks the first paint. The logo stays a
# file: an SVG inside the page can run script in the origin of the app.
if [ ! -s "${INDEX_HTML}" ]; then
  fail "missing or empty: ${INDEX_HTML}. Set INDEX_HTML to the built index.html, or to nothing for a run without one."
fi

# awk reads the two files, then the page, and splices with index and substr:
# sub() would read "&" and "\" of a value as its own syntax. The page can be
# OUT_DIR/index.html itself (`vite preview` starts again on the same build):
# awk reads all of it before the mv, and finds the elements of the last run.
tmp=$(mktemp "${OUT_DIR}/index.html.XXXXXX")
if ! awk '
  FNR == 1 { part++ }
  part == 1 { css = css $0 "\n"; next }
  part == 2 { js = js $0 "\n"; next }
  { page = page (FNR == 1 ? "" : "\n") $0 }

  # Puts element in place of the tag that holds token, up to closing.
  # Returns "" when the page has no such tag.
  function splice(token, closing, element,    at, start, to_close) {
    at = index(page, token)
    if (at == 0) return ""
    start = at
    while (start > 1 && substr(page, start, 1) != "<") start--
    to_close = index(substr(page, at), closing)
    if (to_close == 0) return ""
    return substr(page, 1, start - 1) element \
      substr(page, at + to_close + length(closing) - 1)
  }
  # The element of an earlier run first, then the tag of the build. The
  # build writes its attributes with or without quotes: match the URL only.
  function inline(id, name, url, tag_close, content,    open, closing, result) {
    open = "<" name " id=\"" id "\">"
    closing = "</" name ">"
    result = splice(open, closing, open content closing)
    if (result == "") result = splice(url, tag_close, open content closing)
    if (result == "") {
      print "[entrypoint] " FILENAME ": no tag loads " url > "/dev/stderr"
      exit 1
    }
    page = result
  }

  END {
    inline("institution-theme", "style", "/theme.css", ">", css)
    inline("institution-values", "script", "/injectEnv.js", "</script>", js)
    print page
  }' "${OUT_DIR}/theme.css" "${OUT_DIR}/injectEnv.js" "${INDEX_HTML}" > "${tmp}"; then
  rm -f "${tmp}"
  fail "cannot put the values and the theme into ${INDEX_HTML}"
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/index.html"
# The page holds them now: a leftover file would hide a page that lost them.
rm -f "${OUT_DIR}/theme.css" "${OUT_DIR}/injectEnv.js"

echo "[entrypoint] wrote institution/ and index.html, with the values and the theme, in ${OUT_DIR}"
