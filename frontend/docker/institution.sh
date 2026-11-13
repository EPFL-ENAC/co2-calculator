#!/bin/sh
#
# Builds the institution assets folder and writes theme.css (#3244).
#
# Why this exists: one image serves every institution. The image holds a
# neutral default for every asset: a logo, the browser icons, the login
# illustration and the Geist fonts. The deployment mounts a folder that
# replaces some of them, and that must give theme.conf with the accent
# color. This script copies the defaults, then the files of the mounted
# folder, to OUT_DIR/institution, which nginx serves at /institution/. It
# writes the theme to OUT_DIR/theme.css.
#
# The log names the source of each file, so a deployment that forgets an
# override shows it. A missing theme.conf, a file name that the app does not
# know (a typo) or a bad theme line exits 1, and the nginx entrypoint then
# stops the container.
#
# Runs at container startup as /docker-entrypoint.d/41-institution.sh, after
# 40-inject-env.sh. The dev server and the tests run it too (see
# build/institution.mjs), so the check has one implementation.

set -eu

INSTITUTION_DIR="${INSTITUTION_DIR:-/institution}"
DEFAULT_DIR="${INSTITUTION_DEFAULT_DIR:-/usr/local/share/institution/default}"
OUT_DIR="${OUT_DIR:-/tmp}"
SCRIPT_DIR=$(dirname "$0")
THEME_AWK="${THEME_AWK:-${SCRIPT_DIR}/theme.awk}"

# Keep in sync with the plan 3244-institution-values-assets-theme.md and the
# references in index.html and the logo components. Each one has a default
# in DEFAULT_DIR.
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
  echo "[institution] $1" >&2
  exit 1
}

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
# never serve a half-copied folder.
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
  echo "[institution] ${file}: from ${source}"
done
chmod -R a+rX "${tmp_dir}"
rm -rf "${OUT_DIR}/institution"
mv "${tmp_dir}" "${OUT_DIR}/institution"

# Atomic write, same reason as 40-inject-env.sh: nginx never serves a
# half-written file.
tmp=$(mktemp "${OUT_DIR}/theme.css.XXXXXX")
if ! awk -f "${THEME_AWK}" "${INSTITUTION_DIR}/theme.conf" > "${tmp}"; then
  rm -f "${tmp}"
  fail "invalid theme file ${INSTITUTION_DIR}/theme.conf"
fi
chmod 644 "${tmp}"
mv -f "${tmp}" "${OUT_DIR}/theme.css"

echo "[institution] wrote ${OUT_DIR}/institution and ${OUT_DIR}/theme.css"
