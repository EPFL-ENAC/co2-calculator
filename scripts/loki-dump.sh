#!/usr/bin/env bash
# Dump one UTC calendar day of LokiStack logs for a namespace to NDJSON, for offline analysis.
# Usage: scripts/loki-dump.sh [prod|stage|dev] [YYYY-MM-DD] [logql-filter]
# Auth: your current `oc` login on that cluster (oc login first).
set -euo pipefail

epoch() { python3 -c 'import datetime as d, sys; print(int(d.datetime.fromisoformat(sys.argv[1]).replace(tzinfo=d.timezone.utc).timestamp()))' "$1"; }
ENV="${1:-prod}"; DAY="${2:-$(python3 -c 'import datetime as d; print((d.datetime.now(d.timezone.utc) - d.timedelta(days=1)).date())')}"; FILTER="${3:-}"
case "$ENV" in
  prod)  CL=ocpitsp0001; NS=svc1751p-co2-calculator-prod ;;
  stage) CL=ocpitst0001; NS=svc1751t-co2-calculator-stage ;;
  dev)   CL=ocpitsd0001; NS=svc1751d-co2-calculator-dev ;;
  *) echo "env must be prod|stage|dev" >&2; exit 1 ;;
esac
CTX=$(oc config get-contexts -o name | grep "^$NS/" || true); CTX=${CTX%%$'\n'*}
[ -n "$CTX" ] || { echo "no oc context for $NS: oc login there first" >&2; exit 1; }
# Token goes through a 0600 header file, not argv, so it never shows in ps.
HDR=$(mktemp); chmod 600 "$HDR"; printf 'Authorization: Bearer %s\n' "$(oc --context "$CTX" whoami -t)" > "$HDR"
URL="https://logging-loki-openshift-logging.apps.$CL.xaas.epfl.ch/api/logs/v1/application/loki/api/v1/query_range"
QUERY="{k8s_namespace_name=\"$NS\"} $FILTER"
OUT="loki-$ENV-$DAY.ndjson"
# A failed run must not leave a file that looks like a complete day.
trap 'rm -f "$HDR" "$OUT.partial"' EXIT

# UTC calendar day, to match Loki timestamps. Loki caps a query at 5000
# lines, so step through the day in 5 min windows and refuse a capped one.
start=$(epoch "$DAY"); end=$((start + 86400)); : > "$OUT.partial"
for ((t = start; t < end; t += 300)); do
  chunk=$(curl -sSf -H "@$HDR" "$URL" \
    --data-urlencode "query=$QUERY" --data-urlencode "start=${t}000000000" \
    --data-urlencode "end=$((t + 300))000000000" --data-urlencode limit=5000 \
    --data-urlencode direction=forward -G \
    | jq -c '.data.result[] as $s | $s.values[] | {ts: .[0], labels: $s.stream, line: .[1]}')
  n=$(printf '%s' "$chunk" | grep -c . || true)
  if [ "$n" -ge 5000 ]; then echo "window at $t hit the 5000-line cap: shrink the step" >&2; exit 1; fi
  [ "$n" -gt 0 ] && printf '%s\n' "$chunk" >> "$OUT.partial"
done
mv "$OUT.partial" "$OUT"
echo "$(wc -l < "$OUT") lines -> $OUT"
