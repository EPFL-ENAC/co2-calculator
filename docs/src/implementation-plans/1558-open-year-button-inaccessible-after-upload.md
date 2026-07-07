---
status: proposed
issue: 1558
last_updated: 2026-07-07
title: "Issue 1558 — Headcount upload leaves module permanently 'incomplete', blocking 'Open year for users'"
summary: "A stuck/failed Headcount factor job never satisfies the mandatory_factor check in _annotate_module_incomplete, so anyModuleIncomplete stays true forever and the open-year button never enables even after a full data upload."
---

# Issue 1558 — Cannot open year at the end of data upload (Headcount-triggered)

## Problem

Reporter finishes a full data upload for a year, then the **"Ouvrir l'année pour les utilisateurs"** button in `DataManagementPage.vue` stays disabled, and the calculator shows the year as if it were never opened (no units). Reporter isolated the cause to Headcount: "there's been a problem with headcount data. this problem did not appear at all before."

The button's `:disable` binding is `yearConfigStore.anyModuleIncomplete || is_started` (`frontend/src/pages/back-office/DataManagementPage.vue:401`, `frontend/src/stores/yearConfig.ts:538`). `anyModuleIncomplete` is a pure OR over backend-computed `module.incomplete` flags — the frontend does zero completeness logic itself (source of truth is the backend, per #1215). So a stuck-open button after "the upload finished" means the backend still reports Headcount's module as `incomplete=True`, and it never flips.

## Design

The rollup lives in `backend/app/api/v1/year_configuration.py`:

- `_annotate_module_incomplete` (`year_configuration.py:195-225`) computes, per submodule, `has_factor = sub_val.get("latest_factor_job") is not None or common_factor_present` (`year_configuration.py:242`). If `rules.mandatory_factor and not has_factor` → `"missing_factor"` reason → submodule `incomplete=True` → module `incomplete=True` (`year_configuration.py:243-244`, `225`).
- `submodule_mandatoriness.py:25-26` marks **both** Headcount submodules (`module_type_id=1`, `data_entry_type_id` 1 and 2 — Employee/Student) as `mandatory_factor=True, mandatory_reference=False`. Headcount has no common-factor fallback (`MODULES_REQUIRING_COMMON_FACTOR = {4, 5}` excludes module 1), so `has_factor` depends entirely on `latest_factor_job` being non-null for _each_ headcount submodule.
- `latest_factor_job` is populated by `_pick_latest_job` (`year_configuration.py:250-278`) against `data_ingestion_jobs` rows for `(module_id, sub_id, target=FACTOR)`. Per its own docstring (`year_configuration.py:178-180`), **presence** of a job record satisfies the check regardless of state — `"An errored job (result == 2) is NOT missing"`. So a job that reached `FINISHED/ERROR` is fine; the failure mode is a job that never reaches a terminal row at all, or reaches it under a key `_pick_latest_job` doesn't match.

Hypothesis: a Headcount factor upload that fails mid-ingestion — e.g., the enqueue writes the `data_ingestion_jobs` row but the worker never marks it `FINISHED`/`ERROR` (crashes, times out, or throws before the state transition), or writes it with the wrong `(module_id, sub_id, target_type, ingestion_method)` tuple (e.g. a code path that swapped Employee/Student `data_entry_type_id`, or used `MANUAL`/`API` instead of the expected method) — leaves `latest_factor_job` `None` for that submodule indefinitely. `has_factor` then evaluates `False` on _every_ subsequent GET, `missing_factor` is appended every time, and `module.incomplete` for Headcount is pinned `True` forever, no matter how many times the operator re-uploads valid data afterward, _unless_ the re-upload happens to target the exact same lookup key the first, broken upload missed. This matches "did not appear before" — a regression in the Headcount ingestion/factor-job-write path, not a general completeness-check bug (Buildings/Travel/etc. use the same `_annotate_module_incomplete` machinery and are not reported broken).

Also plausible but lower priority: a genuinely orphaned/duplicate Headcount submodule row in `year_configuration.config` (e.g., seeded with a stale `data_entry_type_id` no longer in `SUBMODULE_MANDATORINESS`, defaulting to `_DEFAULT_MANDATORINESS` = not mandatory — this direction would _unblock_ incorrectly, so it doesn't fit the report) — kept here only to rule it out during investigation, not the leading hypothesis.

## Steps

- [ ] Reproduce: seed/select a year, run a Headcount factor upload that is forced to fail after the `data_ingestion_jobs` row is created but before it's marked `FINISHED`/`ERROR` (kill the worker mid-job, or inject a raised exception post-insert in the Headcount ingestion handler in `backend/app/tasks/ingestion_tasks.py`). Confirm via `GET /year-configuration/{year}` that `modules["1"].submodules["1"].incomplete == True` with `incomplete_reasons == ["missing_factor"]`, and that `modules["1"].incomplete == True` persists.
- [ ] Confirm the stuck state survives a subsequent, successful Headcount factor re-upload — check whether `_pick_latest_job` is keyed correctly (module_id=1, sub_id matches Employee=1/Student=2, target=FACTOR, and whichever `ingestion_method` the Headcount upload path actually writes) and whether the re-upload's job row lands under the same key the read path queries.
- [ ] Audit the Headcount ingestion handler for exception paths that leave `data_ingestion_jobs` in a non-terminal state (no `FINISHED`/`ERROR` transition) — add a terminal-state guarantee (try/finally or equivalent) so a crashed job always resolves to `ERROR` rather than hanging, since a _present_-but-`ERROR` job already satisfies `has_factor` per current design and would have avoided the deadlock.
- [ ] If a key-mismatch is found (wrong `data_entry_type_id` or `ingestion_method` written by the Headcount path vs. what `_pick_latest_job` queries), fix at the write site — do not special-case the read side for Headcount.
- [ ] Add a regression test in `backend/tests/integration/v1/test_year_configuration*.py` (or the `_annotate_module_incomplete` unit-test module if one exists) asserting: a non-terminal/orphaned Headcount job does not survive as the _only_ signal blocking `incomplete` — i.e., either the ingestion path is fixed to always terminate, or a subsequent successful upload's job correctly supersedes the stuck one in `_pick_latest_job`'s lookup.
- [ ] Manually verify end-to-end: full data upload for a fresh year including Headcount, confirm `anyModuleIncomplete` clears, "Open year for users" enables, click it, confirm units appear in the calculator's workspace selector.
