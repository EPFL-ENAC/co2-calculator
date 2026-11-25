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
# The network list of the chart (#3196). The docker peer and a fake load
# balancer are the trusted proxies: the client is the X-Forwarded-For
# address in front of them, as on the cluster.
cat > "$TMP/geo.conf" <<'GEO'
proxy 172.16.0.0/12;
proxy 192.168.0.0/16;
proxy 10.98.42.0/24;
proxy_recursive;
0.0.0.0/0 1;
::/0 1;
198.51.100.0/24 0;
10.0.0.0/8 0;
172.16.0.0/12 1;
192.168.0.0/16 1;
10.98.42.0/24 1;
GEO
chmod 644 "$TMP/geo.conf"
docker run -d --name "$NAME" -p 127.0.0.1:9466:8080 --read-only \
  -e APP_ENVIRONMENT=production \
  --tmpfs /tmp:uid=101,gid=101 --tmpfs /var/cache/nginx --tmpfs /var/run \
  -v "$PWD/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$TMP/geo.conf:/etc/nginx/client-allowlist/geo.conf:ro" \
  -v "$PWD/docker/entrypoint.sh:/docker-entrypoint.d/40-entrypoint.sh:ro" \
  -v "$PWD/institution-default:/usr/local/share/institution/default:ro" \
  -v "$PWD/institution-example:/institution:ro" \
  -v "$DIST:/usr/share/nginx/html:ro" \
  nginx/nginx-unprivileged:stable-alpine-slim >/dev/null
i=0
until curl -sf "$URL/ready" >/dev/null; do
  i=$((i + 1)); [ "$i" -lt 40 ] || { docker logs "$NAME"; exit 1; }; sleep 0.25
done

JS=$(grep -o '/assets/[^"]*\.js' "$DIST/index.html" | head -1)
CSS=$(grep -o '/assets/[^"]*\.css' "$DIST/index.html" | head -1)
LONG="public, max-age=31536000, immutable"
SHORT="no-cache, must-revalidate"

# fetch PATH ACCEPT_ENCODING: headers to $TMP/h, body to $TMP/b.
# XFF is the client address chain, an allowed address unless a case sets it.
XFF=198.51.100.1
fetch() {
  curl -s -o "$TMP/b" -D "$TMP/h" -H "Accept-Encoding: $2" \
    -H "X-Forwarded-For: $XFF" "$URL$1"
}
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
# A versioned font is kept one year, every fixed name revalidated.
FONT=$(curl -s -H "X-Forwarded-For: $XFF" "$URL/theme.css" | sed -n 's|.*url("\(/institution/font-bold\.[0-9]*\.woff2\)").*|\1|p')
[ -n "$FONT" ] || { echo "FAIL versioned font: none in theme.css"; exit 1; }
echo "ok   versioned font: $FONT"
case_ "font versioned" "$FONT" "" 200 "" font/woff2 "$LONG" ""
case_ "font fixed" /institution/font-bold.woff2 "" 200 "" font/woff2 "$SHORT" ""
case_ "logo fixed" /institution/logo.svg "" 200 "" image/svg+xml "$SHORT" ""
# The same content gives the same ETag after a restart, as on another pod.
fetch /institution/logo.svg ""; ETAG=$(header ETag)
docker restart "$NAME" >/dev/null
i=0
until curl -sf "$URL/ready" >/dev/null; do
  i=$((i + 1)); [ "$i" -lt 40 ] || { docker logs "$NAME"; exit 1; }; sleep 0.25
done
fetch /institution/logo.svg ""; expect "logo after restart" ETag "$ETAG"
# A missing file gets index.html with the 404 status: the body is brotli,
# so the header must say so.
fetch /assets/missing-AAAAAAAA.js br
expect "missing br" status 404; expect "missing br" Content-Encoding br
expect "missing br" Vary Accept-Encoding
fetch /assets/missing-AAAAAAAA.js ""
expect "missing none" status 404; expect "missing none" Content-Encoding ""

# Clients outside the allowed networks (#3196).
XFF="198.51.100.59, 10.98.42.215"
fetch / ""; expect "inside via lb" status 200
# The page is the file of the institution folder, here the image default.
PAGE=institution-default/offnet.html
cmp -s "$TMP/b" "$PAGE" && { echo "FAIL inside via lb: got offnet.html"; exit 1; }
for chain in "203.0.113.5, 10.98.42.215" "198.51.100.9, 203.0.113.5, 10.98.42.215"; do
  XFF=$chain
  # Every path but the page is closed: the app, its files and the probes.
  for path in / /some/route "$JS" /healthz /ready /health /theme.css \
    /injectEnv.js /favicon.ico /institution/logo.svg /institution/offnet.html; do
    fetch "$path" ""; expect "outside $chain $path" status 403
    expect "outside $chain $path" Content-Type text/html
    expect "outside $chain $path" Cache-Control "$SHORT"
    cmp -s "$TMP/b" "$PAGE" || { echo "FAIL outside $path: not offnet.html"; exit 1; }
  done
  # The /tmp copy has no .br: a stale one in the html root must not show.
  fetch / br; expect "outside br" status 403; expect "outside br" Content-Encoding ""
  fetch /offnet.html ""; expect "outside page" status 200
  cmp -s "$TMP/b" "$PAGE" || { echo "FAIL outside page: not offnet.html"; exit 1; }
done
# No header: a direct call, as the kubelet does. Only the probes answer.
XFF=""
for path in /healthz /ready /health; do
  fetch "$path" ""; expect "direct probe $path" status 200
done
fetch / ""; expect "no forwarded header" status 403
# A proxy as the client, inside the wide 10.0.0.0/8: still outside.
XFF="10.98.42.215"
fetch / ""; expect "proxy only" status 403
XFF="10.5.1.1, 10.98.42.215"
fetch / ""; expect "inside 10/8 via lb" status 200
echo "all checks passed"
