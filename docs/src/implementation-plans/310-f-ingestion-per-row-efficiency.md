---
status: delivered
issue: 310-f
last_updated: 2026-06-16
title: "310-f Ingestion per-row efficiency"
summary: "The CSV ingest parse/validate loop dominated wall-clock (~34s for 9555 purchase rows on dev). The first cut guessed line-level suspects and they were wrong. A row-loop profiler was added, and the trace pinned 33.4s of 34.5s on `resolve` — a per-row linear scan of ~23k factor keys in `lookup_data_entry_type_by_kind` (O(rows × factors)). Fixed by memoising the kind→type inference per (kind, subkind); re-measured 34.5s → 1.7s (20×). A one-time index is a documented follow-up, not needed at current data shape."
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
on real data / real DB / real handlers. The actual line for the 9555-row
purchase upload (dev, 2026-06-16):

```
Row-loop profile: 9555 rows in 34.5s (3.61 ms/row) | row=34.2s
  [resolve=33.4 validate=0.2 enrich=0.0 populate=0.0 row_other=0.6]
  loop_overhead=0.3s
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

## Result: `resolve` was 33.4s of 34.5s — and the fix

The trace ended the guessing. Not Pydantic (`validate=0.2`), not DB
(`populate`/`enrich`≈0): **97% of the time was `resolve`**, in
`lookup_data_entry_type_by_kind` (`seed_helper.py`). For every row it linearly
scans **all ~23k factor keys** to infer the row's `data_entry_type` from its
kind:

```python
keys = [k for k in factors_map.keys() if k.__contains__(f":{kind}:")]  # per type, per row
```

That's `O(rows × factors)` ≈ 9555 × 23k ≈ 220M substring checks ≈ 33s — so a CPU
bump barely helps; it's an algorithm problem. (The original "23k factors"
hunch was right, just via a per-row rescan, not memory.)

**Fix (shipped):** the inference is a pure function of `(kind, subkind)`, which
repeat heavily across rows, so memoise it per file on `setup_result` —
`O(rows × factors)` → `O(distinct kinds × factors)`. Same result, computed once
per distinct kind. Mirrors the existing #1415 memoisation of the per-type split.
Regression test: `test_type_inference_is_memoised_per_kind`.

**Re-measured (2026-06-16): 34.5s → 1.7s** — a 20× drop on the same 9555-row
file (`resolve` 33.4s → 1.0s):

```
Row-loop profile: 9555 rows in 1.7s (0.17 ms/row) | row=1.6s
  [resolve=1.0 validate=0.2 enrich=0.0 populate=0.0 row_other=0.5] loop_overhead=0.0s
```

The memo is sufficient at the current data shape — distinct kinds are few, so
the per-distinct-kind scan that remains (the 1.0s) is cheap. **Possible
follow-up, not currently needed:** if a file ever has near-unique kinds per row
(memo ineffective), build a one-time `kind → types` index where the factor pools
are computed and make each lookup O(1). `lookup_data_entry_type_by_kind` has
exactly one caller, so that refactor is self-contained. Deferred — 1.7s is fine.

The method below stays on record for future buckets.

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
