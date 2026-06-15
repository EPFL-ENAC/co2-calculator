---
status: proposed
issue: 310-f
last_updated: 2026-06-15
title: "310-f Ingestion per-row efficiency"
summary: "The CSV ingest parse/validate loop is the dominant cost — ~34s for 9555 rows in the 2026-06-15 dev run, all CPU between the 0.2s delete and the 0.5s COPY. Plan to cut per-row Python work: profile first, then kill redundant calls, batch the per-row DB check, and avoid double validation. Pairs with the progress instrumentation shipped alongside it."
---

# 310-f Ingestion per-row efficiency

> **Status: proposed.** Companion to [[310-e-async-loop-and-pipeline-worker]]
> (which covers loop hygiene + the worker). 310-e makes the loop _yield_
> and _report progress_; 310-f makes it _faster_.

## Why

Measured time map of a 9555-row `MODULE_PER_YEAR` upload (dev, 2026-06-15):

| Phase                                         | Time     |
| --------------------------------------------- | -------- |
| delete prior entries                          | 0.2s     |
| **parse/validate rows (`_process_row` loop)** | **~34s** |
| COPY insert                                   | 0.5s     |
| emission recalc + aggregation                 | ~3s      |

~90% of wall-clock is the per-row Python loop. At ~280 rows/s it's also
what risked event-loop starvation (now mitigated by yielding, not by being
fast). This plan attacks the constant factor.

## Rule 0: profile before optimizing

Add a one-off `cProfile`/`pyinstrument` pass over `_process_row` on a
representative file and rank by cumulative time. Optimize what the profile
says, not what this doc guesses. The items below are the _suspects_ from
reading the code — confirm each before touching it.

## Suspects (from reading `_process_row`)

| #   | Suspect                                                                          | Fix                                                                    | Confidence |
| --- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------- |
| 1   | `_extract_kind_subkind_values` called **twice** per row (lines ~1164 and ~1189)  | Compute once, reuse                                                    | High       |
| 2   | Per-member-row `check_institutional_id_unique` DB round-trip                     | Pre-load existing IDs per module, check in-memory                      | High       |
| 3   | `DataEntry.model_validate` runs **twice** (row build, then `bulk_copy` line 109) | Build once; skip re-validation on the COPY path                        | Med        |
| 4   | `_resolve_handler_and_validate` per row (handler lookup + DTO validate)          | Cache handler by resolved type; memoize validation by column-signature | Med        |
| 5   | `filtered_row` dict-comp + factor-key f-strings rebuilt every row                | Hoist invariants; precompute per-handler column sets                   | Low        |

### 1. Double `_extract_kind_subkind_values`

`_process_row` calls it at line ~1164, then again at ~1189 inside the
factor branch with the same `filtered_row`/`handlers`. Compute once before
the branch and reuse. Pure win, no behaviour change.

### 2. Per-row uniqueness query → batch pre-load

For member entries, `check_institutional_id_unique` issues one query **per
row** (`base_csv_provider.py` ~957). For a multi-thousand-row member CSV
that's the long tail of the 34s. Pre-load existing `user_institutional_id`s
for the in-scope modules once (one indexed query), hold them in a set, and
check membership in memory — the intra-CSV duplicate set
(`seen_institutional_ids`) already works this way; extend it with the
DB-existing set. Keep a final DB unique constraint as the real guard.

### 3. Validate `DataEntry` once

Rows are built into `DataEntry` objects, then `bulk_copy` re-runs
`DataEntry.model_validate` on every one (now chunked, but still O(n) CPU).
If the build path already yields validated instances, the COPY path can
trust them (or use `model_construct` for the trusted internal hop). Verify
nothing downstream depends on the second validation before removing it.

### 4. Handler resolution caching

`_resolve_handler_and_validate` resolves a handler and validates a DTO per
row. Within one file the handler set is fixed; cache the resolved handler
by `data_entry_type` and, where rows share a column signature, memoize the
validation outcome. Measure first — Pydantic validation may dominate or may
be cheap depending on the model.

### 5. Hoist per-row allocations

`filtered_row` comprehension and the factor-lookup key f-strings allocate
per row. Precompute per-handler `expected_columns` as a set (likely already
one) and build keys with `str.join`/tuple keys instead of nested f-strings.
Micro-optimisation — only if the profile flags it.

## Success criteria

- Profile-ranked before/after on the same 9555-row file.
- Target: parse/validate phase **≥2× faster** (≤~15s) without changing
  ingest results (row counts, errors, emissions identical on a fixture).
- No new event-loop starvation — yields from 310-e stay.

## Out of scope

The structural move (worker deployment, threadpool offload) lives in
[[310-e-async-loop-and-pipeline-worker]]. This plan is constant-factor work
on the existing in-loop path; both can land independently.
