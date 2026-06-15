---
status: proposed
issue: 310-f
last_updated: 2026-06-15
title: "310-f Ingestion per-row efficiency"
summary: "The CSV ingest parse/validate loop dominates wall-clock (~34s for 9555 purchase rows on dev). The first cut of this plan guessed line-level suspects and they were wrong (purchase rows aren't `member`, so the batched-uniqueness fix never ran). Rewritten measure-first: a row-loop profiler now logs where the time goes; optimize only the bucket the trace blames, and control for the dev CPU throttle."
---

# 310-f Ingestion per-row efficiency

> **Status: proposed.** Companion to [[310-e-async-loop-and-pipeline-worker]].
> 310-e makes the loop _yield_ (so liveness survives) and _report progress_;
> 310-f makes it _faster_ — **but only after measuring**.

## What the first cut got wrong

The original 310-f listed line-level "suspects" and an attempt was made to fix
them. It moved the needle by ~0s. Two mistakes, both from assuming instead of
measuring:

1. **Purchase rows aren't `member` rows.** The batched-uniqueness win (#2) only
   replaces `check_institutional_id_unique`, which fires **only** for
   `data_entry_type_id == member`. Purchase common data is
   `other_purchases`/`consumable_accessories`/`scientific_equipment`/… — that
   path never executed. Dead optimization for this file.
2. **The yield fix was never a speed fix.** Yielding every 100 rows (310-e)
   stops the liveness restart; it does **not** make the job faster. "Still 34s"
   is the _correct_ outcome of that change, not a failure.

Lesson: **profile before optimizing.** This rewrite makes that the first step.

## Step 0 (shipped): a row-loop profiler

`base_csv_provider` now logs one diagnostic line at the end of the parse phase,
on real data / real DB / real handlers:

```
Row-loop profile: 9555 rows in 33.8s (3.54 ms/row) | row=31.2s
  [resolve=4.1 validate=18.7 enrich=0.2 populate=6.9 row_other=1.3]
  loop_overhead=2.6s
```

Buckets (wall time, accumulated per row via `time.perf_counter`):

| Bucket          | Covers                                                          |
| --------------- | --------------------------------------------------------------- |
| `resolve`       | `_resolve_handler_and_validate` (handler + type resolution)     |
| `validate`      | `handler.validate_create` (Pydantic DTO)                        |
| `enrich`        | `handler.enrich_csv_row` (per-handler hook; DB for some)        |
| `populate`      | `ModuleHandlerService(...)` + `populate_defaults`               |
| `row_other`     | rest of `_process_row`: filter, factor-key build, `DataEntry()` |
| `loop_overhead` | outside `_process_row`: CSV parse, blank skips, progress        |

A **DB-bound** segment (hidden lazy-load N+1) shows as a large bucket dominated
by await time; a **CPU-bound** segment shows as large under no concurrency. The
breakdown tells which, without guessing.

## Step 1: read the trace, then pick the target

Run one real import (the purchase file that took 34s) and read the line. Then,
and only then, optimize the dominant bucket. Candidate fixes per bucket — none
are committed; the trace decides which (if any) apply:

| If dominant     | Likely cause                                                                                        | Candidate fix                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `validate`      | Pydantic re-validates every row                                                                     | Lighter validation (`model_construct` for trusted fields), or validate-by-column-signature memo |
| `populate`      | `ModuleHandlerService` built **per row** (`base_csv_provider.py:1298`); `FactorService` in its ctor | Hoist the service out of the loop (build once, reuse)                                           |
| `resolve`       | per-row handler/type lookup                                                                         | Cache resolved handler by type for the file                                                     |
| `enrich`        | a handler doing a per-row DB lookup                                                                 | Batch the lookup (pre-load once) — note: purchase handlers are likely no-op here                |
| `row_other`     | `filtered_row` dict-comp + factor-key f-strings + `DataEntry()` per row                             | Hoist invariants; build keys with tuples/`join`                                                 |
| `loop_overhead` | CSV re-parse / progress writes                                                                      | Parse once; confirm progress is throttled                                                       |

Static reading (2026-06-15) found **no explicit per-row DB query** in the
purchase path — factor lookup is in-memory by design, module id from an
in-memory map, year from `_year_cache`, and `populate_defaults` reads an
in-memory `factor.values`. So the prior is **CPU-bound** (Pydantic + object
construction). The trace must confirm before any change — static reading cannot
see a SQLAlchemy lazy-load N+1.

## The dev CPU confound — measure on real headroom

The 34s was measured on a dev pod requesting **250m CPU**. A 0.9 ms/row job at
one core reads as ~3.6 ms/row at a throttled quarter-core. Before concluding
"the code is slow," reproduce the trace where CPU isn't throttled (local, or a
right-sized pod). Part of the win may be CPU allocation / the dedicated worker
([[310-e-async-loop-and-pipeline-worker]]), not constant-factor code work.

## Success criteria

- A `Row-loop profile` line captured **before** and **after** any change, same
  file, comparable CPU.
- Target: dominant bucket **≥2× faster**, ingest results byte-identical on a
  fixture (row counts, errors, emissions).
- No regression to the 310-e yields (loop stays responsive).

## Out of scope

The structural move (worker deployment, threadpool offload) is in
[[310-e-async-loop-and-pipeline-worker]]. This plan is constant-factor work on
the in-loop path, gated on the trace.
