---
status: proposed
issue: 1401
last_updated: 2026-07-07
title: "OpenShift stage namespace resource quota headroom"
summary: "Stage namespace is near CPU/memory quota limits per issue #1401's ResourceQuota dump; root cause and target fix are unspecified and need reporter/DevOps clarification before any change."
---

# OpenShift stage namespace resource quota headroom

## Problem

Issue #1401 body is a raw `ResourceQuota` dump for `svc1751t-co2-calculator-stage`, nothing else:

```
spec.hard:  cpu=500m, memory=6Gi, requests.storage=10Gi, services.loadbalancers=0, services.nodeports=0
status.used: cpu=380m, memory=2813Mi, requests.storage=8Gi
```

CPU is at 76% of quota, memory at 47%, storage at 80%. Two screenshots were attached (Grafana/OpenShift graphs, not available here) but the issue has no written description of what's actually wrong or what "optimize" means. Before any code/manifest change, need the reporter or DevOps to clarify which of these is the actual ask:

- Lower per-pod resource **requests** (they may be oversized vs actual usage) — cosmetic, doesn't reduce real consumption.
- Lower actual pod **usage** (memory/CPU leak or inefficiency in backend/frontend) — real optimization.
- **Raise the quota** — administrative ask to DevOps, not a code change.
- Reduce **replica count** — trades availability/throughput for headroom.
- Storage: is the 8Gi/10Gi a DB PVC that needs growth room, or is it also near a ceiling that needs cleanup?

Given the reporter attached graphs but wrote no text, this may simply be a "heads up, watch this" ticket rather than an incident — treat as informational until confirmed otherwise.

## Design

Grep of `helm/` (this repo's only OpenShift/Helm chart, no k8s/openshift/deploy dirs) shows `helm/values.yaml` defines resource requests/limits and replica counts for three chart-owned deployments: backend, frontend, docs. Postgres and Elasticsearch are **not** subcharts (`helm/Chart.yaml` has no `dependencies:` block) — the backend only holds connection secrets (`DB_URL`, `ELASTICSEARCH_HOSTS`, etc.), so those stateful services live elsewhere in (or outside) the namespace and are invisible to this chart.

Current defaults (`helm/values.yaml`), no stage-specific override file exists in this repo:

| Component                           | replicas | cpu request | mem request | mem limit | cpu limit |
| ----------------------------------- | -------- | ----------- | ----------- | --------- | --------- |
| backend                             | 2        | 100m        | 128Mi       | 512Mi     | none      |
| frontend                            | 2        | 50m         | 64Mi        | 256Mi     | none      |
| docs                                | 1        | 50m         | 64Mi        | 256Mi     | none      |
| backend `waitForPostgres` init      | —        | 50m         | 64Mi        | 128Mi     | —         |
| backend `migrations` job (one-shot) | —        | 100m        | 128Mi       | 512Mi     | —         |

Steady-state totals for this chart's own pods: **350m cpu request / 448Mi mem request**. That matches `status.used.cpu` (380m) closely — the extra 30m is plausibly transient (an init/migration container mid-rollout, or rounding). It does **not** explain `status.used.memory` (2813Mi) — 2813Mi is ~6.3x this chart's own request total. That gap means the bulk of memory quota usage in the namespace is coming from something this chart doesn't own or size (Postgres pod, Elasticsearch, another app sharing the namespace, or genuinely higher runtime RSS than the 128Mi/64Mi requests reserve — OpenShift's `status.used` for memory is the sum of pod **requests**, not live RSS, so if actual pods are bursting past their requests toward their limits, that's invisible in this dump and only visible via `kubectl top pods` / Grafana).

No CPU limits are set on any container (only memory limits) — under CPU pressure this lets any one pod burst and starve siblings within the same node/quota; also means the 500m CPU hard cap is the only thing preventing runaway CPU growth cluster-wide.

Investigation angles once the ask is clarified:

1. **Actual usage vs requests**: pull `kubectl top pods -n svc1751t-co2-calculator-stage` (or the Grafana dashboards from the attached screenshots) to see real CPU/mem RSS per pod vs the requests table above. If backend/frontend/docs are running well under their requests, right-sizing requests down is the lazy fix (frees quota headroom with zero behavior change).
2. **Namespace occupants**: enumerate every workload in `svc1751t-co2-calculator-stage` (`kubectl get pods -n ... -o wide` or OpenShift console) to identify what's consuming the ~2.4Gi memory gap this chart doesn't account for — likely Postgres/Elasticsearch or a stray/orphaned pod.
3. **Replica necessity**: backend/frontend run 2 replicas each in stage — confirm stage actually needs HA (vs prod-only), since stage is typically lower-traffic; dropping to 1 replica each would free ~175m cpu / ~224Mi mem request headroom immediately.
4. **Storage**: identify what backs the 8Gi/10Gi `requests.storage` (likely a Postgres PVC) and whether it needs growth room reserved or is close to exhaustion.

## Steps

- [ ] Ask the reporter/DevOps to clarify the actual ask: lower requests, reduce real usage, raise quota, cut replicas, or "just watch this" — issue currently has zero text beyond the quota dump.
- [ ] Pull `kubectl top pods -n svc1751t-co2-calculator-stage` (or the linked Grafana dashboards) to get real CPU/mem usage per pod, compared against the `helm/values.yaml` request table above.
- [ ] Enumerate all workloads in the namespace to find what accounts for the ~2.4Gi memory-request gap between this chart's own pods and `status.used.memory` (2813Mi) — confirm whether Postgres/Elasticsearch/other pods live in-namespace.
- [ ] Confirm whether stage needs 2 replicas for backend/frontend, or whether 1 is acceptable for a non-prod environment — quantify the quota headroom that would free up.
- [ ] Check whether missing CPU `limits` on backend/frontend/docs containers is intentional or should be added to prevent burst-driven CPU quota exhaustion.
- [ ] Identify what backs `requests.storage` (8Gi/10Gi) and whether it's a Postgres PVC needing growth headroom or itself a cleanup target.
- [ ] Based on findings, land the actual fix (right-sized `values.yaml` requests, reduced stage `replicaCount`, or a quota-increase request to DevOps) in a follow-up PR — this plan stops at diagnosis since the ask is unclear.
