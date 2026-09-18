---
status: delivered
issue: 2845
last_updated: 2026-09-17
summary: "The chart's default-deny NetworkPolicy also dropped worker→backend and backend→backend traffic, so the taxonomy-cache broadcast (#2258 follow-up) never reached a pod on dev/stage. One extra policy admits pod-to-pod ingress to the backend port inside the release."
---

# 2845 — Taxonomy cache broadcast blocked by NetworkPolicy

## Symptom

Every `factor_ingest` job on dev ended with three `httpx.ConnectTimeout`
spans on `POST http://<pod-ip>:8000/internal/cache/taxonomy/clear`, one per
live backend pod, all failing at TCP connect inside the 200 ms budget
(trace `b9e7d1…`, job 430, 2026-09-17). The job still succeeded: the
broadcast is best-effort and logs
`taxonomy cache broadcast: pod … unreachable`, then the 60 s TTL takes over.

## Root cause

`helm/templates/network-policies.yaml` applies `default-deny` on Ingress to
every pod and only re-opens the backend port to the OpenShift router
(`networkPolicies.ingressFromRoutes`). No rule admitted traffic from pods of
the release itself, so a SYN from the worker (or another API pod) to
backend:8000 was dropped. Policies are enabled on dev and stage
(`openshift-app-config` overlays), off on prod — the broadcast only worked
where nobody looked.

## Change

- `helm/templates/network-policies.yaml`: new `allow-backend-from-pods`
  policy — ingress to `component: backend` on
  `backend.service.targetPort` from any pod carrying the chart's
  `selectorLabels` (worker and backend alike). Nothing else changes; the
  router rule stays as is.
- `helm/Makefile`: `check-network-policies` renders the chart with policies
  enabled and fails if the pod-to-pod rule is missing — the regression check
  for this fix.

No app code changes. The broadcast module already does the right thing once
the network lets it through.

## Verification

1. `make -C helm check-network-policies` passes.
2. After deploy on dev, run a factor ingest: the worker log no longer prints
   the `unreachable` warning and the trace carries no `ConnectTimeout` spans.

## Left open

- Whether a 3/3 broadcast failure should stay a warning or raise. Today it
  is a silent fallback by design (TTL backstop); this incident shows that a
  permanently dead broadcast is invisible. Decide with the lead; not changed
  here.
- Prod still has `networkPolicies.enabled: false` (see the prod overlay
  comment). Enabling it is an ops change, tracked there, not in this fix.
