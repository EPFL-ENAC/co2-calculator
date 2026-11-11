#!/bin/sh
#
# Institution assets check (#500).
#
# Why this exists: the image ships no logo, icon or font of its own. Each
# deployment mounts its institution folder at /usr/share/nginx/html/institution
# (a docker compose volume, or a Helm volume, see helm/values.yaml
# frontend.institutionAssets). Without it every page renders broken images,
# so the container stops here and names the missing files instead.
#
# Runs from the nginx-unprivileged base image's /docker-entrypoint.d/ hook,
# before 40-inject-env.sh. The stock entrypoint stops the container when a
# hook script fails.
set -eu

ASSETS_DIR=/usr/share/nginx/html/institution

missing=""
for file in logo.svg favicon.ico apple-touch-icon.png login-illustration.svg fonts.css; do
  if [ ! -f "${ASSETS_DIR}/${file}" ]; then
    missing="${missing} ${file}"
  fi
done

if [ -n "${missing}" ]; then
  echo "[institution-assets] missing in ${ASSETS_DIR}:${missing}" >&2
  echo "[institution-assets] mount the institution assets folder there (frontend/institution/epfl is the EPFL one)" >&2
  exit 1
fi

echo "[institution-assets] ${ASSETS_DIR} has every required file"
