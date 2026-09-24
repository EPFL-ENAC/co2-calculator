---
status: in-progress
issue: 2934
last_updated: 2026-09-24
summary: "A 24 h prod Loki dump was 97% probe access lines and collector self-warnings; drop both at the source, delete per-evaluation policy chatter, and ship the dump script so the next audit takes one command."
---

# Clean prod logs: probes, collector conflict, policy chatter

Issue [#2934](https://github.com/EPFL-ENAC/co2-calculator/issues/2934) holds
the full audit of the 2026-09-23 dump, the scored option table, and the
preferred end-state design (single sliding session cookie, logs as events).
This plan covers the low-risk slice: no behaviour change, no auth change.

## What ships

| change                                                                                            | where                                                              | removes                                                         |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------- |
| Drop `uvicorn.access` lines for 200 answers to `/healthz` and `/ready`                            | `backend/app/core/logging.py`                                      | ~35 k lines/day (backend + worker)                              |
| Disable `urllib`, `urllib3`, `requests` OTel instrumentations                                     | `helm/values.yaml` **and** every overlay in `openshift-app-config` | 46 k collector "Instrument description conflict" lines/day      |
| Delete "Permission granted" / "Permission denied" / "Module permission check" per-evaluation logs | `backend/app/core/policy.py`                                       | 62 INFO + 2 false WARNING lines/day                             |
| `scripts/loki-dump.sh`                                                                            | new                                                                | one command to dump a day of any env from the LokiStack gateway |

The collector conflict: `urllib` and `urllib3` describe `http.client.duration`
as "Measures the duration…" while `httpx`, `aiohttp` and `requests` say
"measures…", and the Prometheus exporter reports the clash on every scrape.
Nothing consumes the metric for those three libraries (the app's outbound
calls use httpx; S3 keeps its botocore spans). The env var is overridden in
each `openshift-app-config` overlay, so that repo gets a matching PR.

Non-200 probe answers still log. A real 403 still logs through the module
permission check's "denied" warning and the access line.

## Out of scope, tracked in the issue

- `GET /session` answering 200 and the single sliding cookie (needs its own
  reviewed plan, auth).
- Turning the access log off in favour of one request-line middleware.

## Verification

- `uv run pytest tests/unit/core/test_logging_probe_filter.py`
- After deploy: `scripts/loki-dump.sh prod` for a full day, then
  `jq -r '.labels.k8s_container_name'` counts. Expected: worker near zero,
  otel-collector zero, backend only real traffic.
