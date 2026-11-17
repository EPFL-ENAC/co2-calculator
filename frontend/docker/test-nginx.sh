#!/bin/sh
# Proves the compression negotiation of nginx.conf on the real base image.
# Usage: sh docker/test-nginx.sh dist/spa (after build/precompress.mjs).
# Why: nginx has no brotli module, the .br files are served by plain rules,
# and a wrong Content-Encoding or Content-Type breaks every page.
set -eu
DIST=$(cd "$1" && pwd)
cd "$(dirname "$0")/.."
NAME=co2-perf-brotli
URL=http://127.0.0.1:9466
TMP=$(mktemp -d)
trap 'docker rm -f "$NAME" >/dev/null 2>&1; rm -rf "$TMP"' EXIT
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p 127.0.0.1:9466:8080 --read-only \
  --tmpfs /tmp:uid=101,gid=101 --tmpfs /var/cache/nginx --tmpfs /var/run \
  --env-file ../institutions/epfl/frontend.env.example \
  -v "$PWD/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/docker/entrypoint.sh:/docker-entrypoint.d/40-entrypoint.sh:ro" \
  -v "$PWD/institution-default:/usr/local/share/institution/default:ro" \
  -v "$PWD/tests/institution:/institution:ro" \
  -v "$DIST:/usr/share/nginx/html:ro" \
  nginxinc/nginx-unprivileged:stable-alpine-slim >/dev/null
i=0
until curl -sf "$URL/ready" >/dev/null; do
  i=$((i + 1)); [ "$i" -lt 40 ] || { docker logs "$NAME"; exit 1; }; sleep 0.25
done

JS=$(grep -o '/assets/[^"]*\.js' "$DIST/index.html" | head -1)
CSS=$(grep -o '/assets/[^"]*\.css' "$DIST/index.html" | head -1)
LONG="public, max-age=31536000, immutable"
SHORT="no-cache, must-revalidate"

# fetch PATH ACCEPT_ENCODING: headers to $TMP/h, body to $TMP/b.
fetch() { curl -s -o "$TMP/b" -D "$TMP/h" -H "Accept-Encoding: $2" "$URL$1"; }
header() { grep -i "^$1:" "$TMP/h" | head -1 | cut -d' ' -f2- | tr -d '\r'; }
status() { head -1 "$TMP/h" | cut -d' ' -f2; }
# expect LABEL NAME VALUE: NAME is a header, or "status"; VALUE "" = absent.
expect() {
  got=$(if [ "$2" = status ]; then status; else header "$2"; fi)
  [ "$got" = "$3" ] || { echo "FAIL $1: $2 is '$got', want '$3'"; exit 1; }
  echo "ok   $1: $2 = '$3'"
}
# case LABEL PATH ACCEPT STATUS ENCODING TYPE CACHE VARY
case_() {
  fetch "$2" "$3"
  expect "$1" status "$4"; expect "$1" Content-Encoding "$5"
  expect "$1" Content-Type "$6"; expect "$1" Cache-Control "$7"
  expect "$1" Vary "$8"; expect "$1" X-Content-Type-Options nosniff
}
JST=application/javascript
case_ "js br" "$JS" br 200 br $JST "$LONG" Accept-Encoding
node -e 'const z=require("zlib"),f=require("fs");process.exit(Buffer.compare(z.brotliDecompressSync(f.readFileSync(process.argv[1])),f.readFileSync(process.argv[2])))' "$TMP/b" "$DIST$JS" \
  || { echo "FAIL js br: decoded body differs"; exit 1; }
echo "ok   js br: decoded body equals $JS"
case_ "js br,gzip" "$JS" "br, gzip" 200 br $JST "$LONG" Accept-Encoding
case_ "js gzip" "$JS" gzip 200 gzip $JST "$LONG" Accept-Encoding
case_ "js none" "$JS" "" 200 "" $JST "$LONG" Accept-Encoding
case_ "js identity" "$JS" identity 200 "" $JST "$LONG" Accept-Encoding
case_ "js br;q=0" "$JS" "br;q=0, gzip" 200 gzip $JST "$LONG" Accept-Encoding
case_ "css br" "$CSS" br 200 br text/css "$LONG" Accept-Encoding
case_ "index br" / br 200 br text/html "$SHORT" Accept-Encoding
case_ "route br" /some/route "br, gzip" 200 br text/html "$SHORT" Accept-Encoding
case_ "injectEnv br" /injectEnv.js "br, gzip" 200 gzip $JST "$SHORT" Accept-Encoding
case_ "png br" /institution/favicon-32x32.png br 200 "" image/png "$SHORT" ""
fetch "$JS.br" br; expect "direct .br" status 404
echo "all checks passed"
