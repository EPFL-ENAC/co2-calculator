#!/usr/bin/env bash
# Dump one calendar day of LokiStack logs for a namespace to NDJSON, for offline analysis.
# Usage: scripts/loki-dump.sh [prod|stage|dev] [YYYY-MM-DD] [logql-filter]
# Auth: your current `oc` login on that cluster (oc login first).
set -euo pipefail

ENV="${1:-prod}"; DAY="${2:-$(date -v-1d +%F)}"; FILTER="${3:-}"
case "$ENV" in
  prod)  CL=ocpitsp0001; NS=svc1751p-co2-calculator-prod ;;
  stage) CL=ocpitst0001; NS=svc1751t-co2-calculator-stage ;;
  dev)   CL=ocpitsd0001; NS=svc1751d-co2-calculator-dev ;;
  *) echo "env must be prod|stage|dev" >&2; exit 1 ;;
esac
CTX="$NS/api-$CL-xaas-epfl-ch:6443/$(whoami)"
TOKEN=$(oc --context "$CTX" whoami -t)
URL="https://logging-loki-openshift-logging.apps.$CL.xaas.epfl.ch/api/logs/v1/application/loki/api/v1/query_range"
QUERY="{k8s_namespace_name=\"$NS\"} $FILTER"
OUT="loki-$ENV-$DAY.ndjson"

# Loki caps a query at 5000 lines; step through the day in 5 min windows.
start=$(date -j -f "%F %T" "$DAY 00:00:00" +%s); end=$((start + 86400)); : > "$OUT"
for ((t = start; t < end; t += 300)); do
  curl -sf -H "Authorization: Bearer $TOKEN" "$URL" \
    --data-urlencode "query=$QUERY" --data-urlencode "start=${t}000000000" \
    --data-urlencode "end=$((t + 300))000000000" --data-urlencode limit=5000 \
    --data-urlencode direction=forward -G \
    | jq -c '.data.result[] as $s | $s.values[] | {ts: .[0], labels: $s.stream, line: .[1]}' >> "$OUT"
done
echo "$(wc -l < "$OUT") lines -> $OUT"
