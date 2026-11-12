#!/bin/sh
#
# Checks the institution assets folder and writes theme.css (#3244).
#
# Why this exists: one image serves every institution. The deployment mounts
# a folder with the logo, the browser icons, the login illustration, the fonts
# and the theme file. nginx serves the folder at /institution/ and the
# generated theme at /theme.css. A missing file or a bad theme line exits 1,
# and the nginx entrypoint then stops the container, so an institution never
# gets an app with a broken logo or the wrong colors.
#
# Runs at container startup as /docker-entrypoint.d/41-institution.sh, after
# 40-inject-env.sh. The dev server and the tests run it too (see
# build/institution-plugin.js), so the check has one implementation.

set -eu

INSTITUTION_DIR="${INSTITUTION_DIR:-/institution}"
OUT_DIR="${OUT_DIR:-/tmp}"
SCRIPT_DIR=$(dirname "$0")
THEME_AWK="${THEME_AWK:-${SCRIPT_DIR}/theme.awk}"

# Keep in sync with the plan 3244-institution-values-assets-theme.md and the
# references in index.html, css/00-fonts/_fonts.scss and the logo components.
REQUIRED_FILES="
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
theme.conf
"

missing=""
for file in ${REQUIRED_FILES}; do
  if [ ! -s "${INSTITUTION_DIR}/${file}" ]; then
    missing="${missing} ${file}"
  fi
done
if [ -n "${missing}" ]; then
  echo "[institution] missing or empty in ${INSTITUTION_DIR}:${missing}" >&2
  exit 1
fi

# Atomic write, same reason as 40-inject-env.sh: nginx never serves a
# half-written file.
tmp=$(mktemp "${OUT_DIR}/theme.css.XXXXXX")
if ! awk -f "${THEME_AWK}" "${INSTITUTION_DIR}/theme.conf" > "${tmp}"; then
  rm -f "${tmp}"
  echo "[institution] invalid theme file ${INSTITUTION_DIR}/theme.conf" >&2
  exit 1
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/theme.css"

echo "[institution] checked ${INSTITUTION_DIR} and wrote ${OUT_DIR}/theme.css"
