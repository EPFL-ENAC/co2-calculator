---
status: delivered
issue: 2404
last_updated: 2026-08-26
title: "Factor-resolution expression indexes"
summary: "The submodule listing's per-row factor lookup scanned the det's whole factor set for every page row (2.08 ms/row over 1219 candidates). Ships 8 partial expression indexes on factors — one per distinct handler kind_field — measured 10× per evaluation, 664 kB total. The 14 s incident itself was stale statistics + cold cache, not the subquery; the structural page-first fix is a follow-up."
---

# Factor-resolution expression indexes (#2404)

One `EXPLAIN` at a time, this went from "one query is 99.7% of a 14 s
request" to three separate findings. The issue thread carries the full
plans; this records what shipped and what it deliberately did not.

## What the measurements actually showed

- **The correlated subquery was real but not the incident.**
  `_resolved_factor_id` evaluates a `classification->>kind_field` equality
  per page row — 2.08 ms/row over 1 219 candidate factors, unindexable as
  written. But the full page query, warm, ran in **24.9 ms** with
  `SubPlan loops=20`: the join is evaluated lazily after the limit.
- **The 14 s was environmental, twice over.** Planner estimates were off
  **2000×** (`rows=2` vs 4 000 actual — stale statistics after bulk
  ingest), which makes plan choice a coin flip; and 20 912 buffers were
  all `shared hit` warm — cold, ~19 k random DBaaS reads is 10–40 s.
- **The dominant branch isn't factors.** 18 620 of 20 912 buffers are the
  emission aggregate, which touches **all 4 000** module entries to serve
  a 20-row page.

## Shipped

8 partial expression indexes (`ix_factors_res_<key>`), one per distinct
handler `kind_field`, columns `(data_entry_type_id, year,
(classification->>key))`, partial on `key IS NOT NULL` so each stores only
rows carrying its key — **664 kB total** on 37 972 factor rows. Measured
10× per evaluation (2.08 → 0.19 ms) and a 3× buffer cut on the factor
branch.

Keys live in `FACTOR_RESOLUTION_INDEX_KEYS` (`app/models/factor.py`), a
hand-maintained list — deriving it from the handler registry would create
a models → schemas import cycle. `test_factor_resolution_indexes` pins the
list against the live registry, which already caught one miss:
`purchase_category` is declared assignment-style in
`modules_planner/purchase/handlers.py` and every grep census missed it.

Migration `ef0ef41fc242` uses `if_not_exists`/`if_exists` — dev carries
hand-created copies from the investigation, and the migration adopts
rather than fails. Round-tripped locally (upgrade → downgrade → upgrade).

## Deliberately not here

- **Page-first restructure of `get_submodule_data`** — the structural fix.
  Aggregate emissions and resolve factors for the paged 20 ids only, when
  sort/filter reference no `Factor`/emission column; keep today's shape
  when they do. Makes cost proportional to the page instead of the module,
  which is what actually protects against the cold-cache recurrence. Needs
  tests pinning _which factor_ resolves and _which totals_ return through
  both paths. Follow-up on #2404.
- **`ANALYZE` after bulk ingest** — the 2000× estimate error is a pipeline
  hygiene question and touches ingestion internals; proposed on the issue,
  not implemented.
