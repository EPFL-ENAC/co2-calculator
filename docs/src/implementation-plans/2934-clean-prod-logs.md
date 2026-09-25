---
status: delivered
issue: 2934
last_updated: 2026-09-24
summary: "A 24 h prod Loki dump was 97% probe access lines and collector self-warnings; drop the probe lines at the source, delete per-evaluation policy chatter, route every 403 gate through one logged helper, and ship the dump script; the collector fix is config in openshift-app-config."
---

# Clean prod logs: probes, collector conflict, policy chatter

Issue [#2934](https://github.com/EPFL-ENAC/co2-calculator/issues/2934) holds
the full audit of the 2026-09-23 dump, the scored option table, and the
preferred end-state design (single sliding session cookie, logs as events).
This plan covers the low-risk slice: no behaviour change, no auth change.

## What ships

| change                                                                                            | where                         | removes                                                         |
| ------------------------------------------------------------------------------------------------- | ----------------------------- | --------------------------------------------------------------- |
| Drop `uvicorn.access` lines for 200 answers to `/healthz` and `/ready`                            | `backend/app/core/logging.py` | ~35 k lines/day (backend + worker)                              |
| Delete "Permission granted" / "Permission denied" / "Module permission check" per-evaluation logs | `backend/app/core/policy.py`  | 62 INFO + 2 false WARNING lines/day                             |
| `scripts/loki-dump.sh`                                                                            | new                           | one command to dump a day of any env from the LokiStack gateway |

The collector conflict (46 k lines/day) is `urllib3` describing
`http.client.duration` as "Measures the duration…" while `httpx` and
`aiohttp` say "measures…". Disabling the urllib3 instrumentation would also
drop the only spans the sync Elasticsearch client produces, so the fix is
collector-side in `openshift-app-config`: a `transform` processor that
normalises the description. Tracked in openshift-app-config, not in this PR.

Non-200 probe answers still log. A real 403 logs once, with user_id and
permission path: `check_module_permission` for module gates, and
`check_permission` for the six backoffice gates in `files.py` and
`year_configuration.py`, which used to inline `is_permitted` + raise and
relied on the deleted per-evaluation line for their only trace.

Still logged per evaluation, deliberately left: the "Data filter: … scope"
INFO lines in `_evaluate_data_filter_policy`. They fire once per list call,
not per scope probe, and describe the scope actually applied.

## Out of scope, tracked in the issue

- `GET /session` answering 200 and the single sliding cookie: #2943, plan
  and ADR-020 in PR #2944.
- Turning the access log off in favour of one request-line middleware.

## Verification

- `uv run pytest tests/unit/core/test_logging_probe_filter.py`
- After deploy: `scripts/loki-dump.sh prod` for a full day, then
  `jq -r '.labels.k8s_container_name'` counts. Expected: worker near zero,
  otel-collector zero, backend only real traffic.
