#!/bin/sh
# Proves the client check of nginx.conf on the real base image (#3196).
# Usage: sh test-nginx.sh. Why: a client outside the allowed networks must
# never read the docs, and a forged X-Forwarded-For must not change that.
set -eu
cd "$(dirname "$0")"
NAME=co2-docs-nginx
URL=http://127.0.0.1:9467
TMP=$(mktemp -d)
trap 'docker rm -f "$NAME" >/dev/null 2>&1; rm -rf "$TMP"' EXIT
mkdir "$TMP/html" && echo docs > "$TMP/html/index.html"
# The docker peer and a fake load balancer are the trusted proxies.
printf '%s\n' 'proxy 172.16.0.0/12;' 'proxy 192.168.0.0/16;' \
  'proxy 10.98.42.0/24;' 'proxy_recursive;' '0.0.0.0/0 1;' '::/0 1;' \
  '198.51.100.0/24 0;' '10.0.0.0/8 0;' '172.16.0.0/12 1;' \
  '192.168.0.0/16 1;' '10.98.42.0/24 1;' > "$TMP/geo.conf"
chmod -R a+rX "$TMP"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p 127.0.0.1:9467:8080 --read-only \
  --tmpfs /tmp --tmpfs /var/cache/nginx --tmpfs /var/run \
  -v "$PWD/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$TMP/geo.conf:/etc/nginx/client-allowlist/geo.conf:ro" \
  -v "$TMP/html:/usr/share/nginx/html:ro" \
  nginx/nginx-unprivileged:stable-alpine-slim >/dev/null
i=0
until curl -sf "$URL/healthz" >/dev/null; do
  i=$((i + 1)); [ "$i" -lt 40 ] || { docker logs "$NAME"; exit 1; }; sleep 0.25
done
# expect LABEL XFF PATH STATUS LOCATION
expect() {
  got=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' \
    -H "X-Forwarded-For: $2" "$URL$3")
  want="$4 $5"
  [ "$got" = "$want" ] || [ "$got" = "$4 http://127.0.0.1:9467$5" ] \
    || { echo "FAIL $1: got '$got', want '$want'"; exit 1; }
  echo "ok   $1: $got"
}
expect "inside via lb" "198.51.100.59, 10.98.42.215" / 200 ""
expect "outside" "203.0.113.5, 10.98.42.215" /some/page 302 /
expect "forged chain" "198.51.100.9, 203.0.113.5, 10.98.42.215" / 302 /
expect "no header" "" / 302 /
# No header: a direct call, as the kubelet does. With it, the probe is closed.
expect "direct probe" "" /healthz 200 ""
expect "probe outside" "203.0.113.5, 10.98.42.215" /healthz 302 /
expect "probe inside via lb" "198.51.100.59, 10.98.42.215" /healthz 200 ""
expect "proxy only" "10.98.42.215" / 302 /
expect "inside 10/8 via lb" "10.5.1.1, 10.98.42.215" / 200 ""
LOCATION=$(curl -s -D - -o /dev/null -H "X-Forwarded-For: 203.0.113.5" "$URL/" \
  | sed -n 's/^[Ll]ocation: *//p' | tr -d '\r')
[ "$LOCATION" = "/" ] || { echo "FAIL relative redirect: '$LOCATION'"; exit 1; }
echo "ok   relative redirect: $LOCATION"
echo "all checks passed"
