---
status: in-progress
issue: 2623
last_updated: 2026-09-02
summary: "Count role sync's suspicious-empty and provider-unavailable
  skips as an OTel metric, and alert on it in openshift-app-config — the
  guard from #2531/#2538 logged at ERROR but nothing was ever notified."
---

# 2623 — Alert on role sync's suspicious-empty guard

## The gap

[#2538](https://github.com/EPFL-ENAC/co2-calculator/pull/2538) added a
guard that refuses to wipe a user's roles on an ambiguous empty response
and logs at ERROR instead. That stops the damage; it does not make the
_event_ visible to anyone — it was a log line nobody was notified about.
No metric, no backend error tracking (Sentry/GlitchTip is frontend-only —
`APP_SENTRY_DSN`), and no HTTP signal (the sync runs in a `BackgroundTask`,
so the triggering request already returned 200). This was proposed in
#2531's own original issue body (proposed fix, item 5: "alert on it — a
metric, not just a log line") but never made it into #2538 or #2539.

## What shipped

### Backend counter (`app/services/role_sync_service.py`, shared with #2539)

```python
_role_sync_skipped = get_meter(__name__).create_counter(
    "role_sync.skipped",
    unit="{sync}",
    description="Role sync outcomes that left a user's stored roles untouched",
)
```

Mirrors the existing `app/db.py` pattern (`db.pool.timeouts`,
`db.connect.failures` — both from #2572). Incremented with
`{"outcome": ...}` on `RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY` and
`SKIPPED_PROVIDER_UNAVAILABLE`. The existing OTel collector pipeline
exports it to Prometheus as `role_sync_skipped_total{outcome=...}` — no new
infrastructure, same plumbing the existing request-latency alerting rides
on.

### Alert rule (`openshift-app-config`, all three envs)

Added to `epfl/co2-calculator/overlays/{dev,stage,prod}/monitoring/specific-namespace-alerts.yaml`,
following the exact sparse-counter two-arm pattern `DbPoolCheckoutTimeout`
/ `DbServerConnectionSlotsExhausted` already use (#2572/#2573) — `increase()`
for later events, plus an `unless ... offset` arm to catch the series'
_birth_ (which `increase()` reads as no increase, and the very first event
ever is the incident itself). No `absent()` deadman is possible for the
same reason an event counter's silence is indistinguishable from health.

No dashboard panel — #2572's sibling counters didn't get one either
(sparse revocation-adjacent events are alert-worthy, not
trend-worthy; a panel with near-permanently-empty data isn't useful).

## Not in scope

Whether an empty response should count as a revocation at all is
[#2539](https://github.com/EPFL-ENAC/co2-calculator/issues/2539)'s
question, not this one's — this issue is purely "make the existing guard's
ERROR log reach someone," independent of how #2539's two-strikes design
works.
