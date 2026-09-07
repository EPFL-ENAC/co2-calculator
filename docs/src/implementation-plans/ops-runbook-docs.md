---
status: delivered
issue: none
last_updated: 2026-09-07
summary: Day-to-day operations documentation — an incident landing page, a tools-and-access page, and a rewritten infra overview with every stale ops claim removed.
---

# Ops runbook and tools documentation

## Problem

The developer docs had no day-to-day operations entry point. The triage
content (service map, DSI queues) sat under "Security Documentation";
the tool URLs (Grafana, ArgoCD, console logs) lived only as hardcoded
strings in `frontend/src/pages/system/LogsPage.vue`; Tempo, Icinga,
GlitchTip and Matomo were not linked anywhere. `infra/01-overview.md`
described Jaeger, Kibana, Elasticsearch, `grafana.epfl.ch`, and
hand-managed stage/prod secrets, none of which exist today. Everything
else lived in the lead developer's head.

## Decisions

- Internal dashboard hostnames are accepted as public: they already ship
  in the public repo and sit behind VPN and SSO. The docs link them.
- Secret locations stay out of the public docs beyond the vault hostname.
  Names, emails and restore commands stay in the private ops repo.
- No new pattern: pages live under the existing `infra/` folder, the nav
  section is renamed "Infrastructure & Operations" and the incident page
  goes first.

## Delivered

- `infra/04-operations.md` — what to expect, first ten minutes, links per
  environment, symptom-to-owner map with DSI queues (moved from the
  security page), our-side symptom table, recovery, after the incident.
- `infra/05-tools-and-access.md` — every tool, what it is for, how to get
  in; the EPFL service account and groups behind the service; onboarding
  steps.
- `infra/01-overview.md` — rewritten from the GitOps overlays: routes,
  namespaces, what runs in a namespace, deploy path, secrets, backups.
- Stale claims removed from `02-system-overview`, `03-subsystem-map`,
  `05-environments`, `07-global-conventions`, `11-deployment-topology`,
  `encryption`: Jaeger, Azure Key Vault, manual stage/prod secrets.
- `security-documentation.md` points at the operations page for the
  service map. `frontend/error-monitoring.md` no longer links the vault
  project. Home page gets a "Something is broken?" entry.

## Follow-ups

- `infra/06-debugging-with-traces.md`: trace-based debugging recipes,
  reconstructed from plans 2360, 2404, 2449, 2566, 2531, 1958, 2050,
  2226, 2170, 2145, 2302, 2371, 2372, 2397 and their issues.
- Which EPFL group feeds the `admin-SVC1751` rolebinding, and what
  `co2-calculator-ops` actually grants. Two groups exist by accident;
  kept both on 2026-09-07 until understood, then merge into one.
- Verify end to end that a GlitchTip `trace_id` finds its backend spans
  in Tempo; the docs say "expected, not verified" until then.
- Renew service account `svc-calcco2-epfl-api` before 2026-10-20.
