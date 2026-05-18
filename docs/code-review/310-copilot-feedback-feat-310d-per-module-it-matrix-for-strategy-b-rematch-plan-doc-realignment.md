# Bot Review TODOs: PR #1042

## Source Branch: `feat/310d-followup-strategy-b-rematch`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds documentation for Plan 310-D rematch behavior and scaffolds a follow-up plan for handling Strategy B / FK-linked modules, extending the existing emission pipeline reference docs.

**Changes:**

- Updated the emission pipeline flow reference with a new “Rematch” section describing how factor changes propagate.
- Added a new implementation plan document outlining the Strategy B rematch approach and proposed integration test coverage.
- Refreshed doc frontmatter metadata (last_updated/summary) for the pipeline-flow page.

### Reviewed changes

Copilot reviewed 2 out of 2 changed files in this pull request and generated 5 comments.

| File                                                      | Description                                                                              |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| docs/src/implementation-plans/emission-pipeline-flow.md   | Adds a rematch reference section and updates the page summary/last_updated.              |
| docs/src/implementation-plans/310-d-strategy-b-rematch.md | New plan doc describing the Strategy B/FK-link rematch follow-up and proposed IT matrix. |

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 4 out of 4 changed files in this pull request and generated 4 comments.

---

### File: `docs/src/implementation-plans/emission-pipeline-flow.md` (Line 155) — Copilot

In the numbered list under "Plan 310-D Rematch Contract", the continuation line for item 1 ("year) in one query…") is not indented, so Markdown will likely break the list formatting. Indent that wrapped line (and any other wraps) so it renders as a single list item.

---

### File: `docs/src/implementation-plans/emission-pipeline-flow.md` (Line 156) — Copilot

## This section states the rematch uses a "Single bulk-fetch" with "No per-entry DB roundtrips" and marks the JSON-link path as delivered. In the current codebase, `EmissionRecalculationWorkflow.recalculate_for_data_entry_type` still does a per-entry `resolve_primary_factor_id` call (N+1) and does not implement the described bulk lookup yet. Please either (a) adjust wording/status to make it explicit this behavior is pending PR #1027, or (b) update the doc to match the current implementation if this doc is intended to be accurate on its own.

### File: `docs/src/implementation-plans/310-d-strategy-b-rematch.md` (Line 18) — Copilot

## The context section says Plan 310-D rematch "landed in PR #1027", but this PR description notes #1027 is still in review. To avoid the doc becoming incorrect if merged before #1027, consider phrasing like "proposed in" / "to be landed in" and/or link it as a dependency.

### File: `docs/src/implementation-plans/310-d-strategy-b-rematch.md` (Line 144) — Copilot

## The integration-test planning details are internally inconsistent: the coverage matrix lists 15 rows (6 FK-link rows), but the text refers to "14 test bodies" and the "Critical files"/"Verification" sections mention only 4 Strategy B ITs and 9 Strategy A ITs. Please reconcile the intended counts/scope (e.g., clarify whether one row is already covered, whether Strategy B tests are 4 vs 6, and whether Strategy A includes equipment/it).

### File: `docs/src/implementation-plans/310-d-strategy-b-rematch.md` (Line 99) — Copilot

The file path referenced for embodied energy verification is inconsistent with the rest of the doc/repo structure: the workflow lives at `backend/app/workflows/embodied_energy.py` (imported as `app.workflows.embodied_energy`), not `app/workflows/embodied_energy.py`. Updating the path here will make it easier to locate the file.

---

### File: `docs/src/implementation-plans/emission-pipeline-flow.md` (Line 147) — Copilot

The rematch table classifies “Buildings — Rooms” as FK-link (`data_entry_emissions.primary_factor_id`), but `BuildingRoomModuleHandler` uses `primary_factor_id` from `entry.data` (JSON-link) and `kind_field='building_name'`/`subkind_field='room_type'` are on the entry. Consider moving Buildings — Rooms to the JSON-link row (and keeping embodied energy under FK-link).

---

### File: `docs/src/implementation-plans/emission-pipeline-flow.md` (Line 166) — Copilot

The “Strict-drop on overall miss” bullet says the recomputed `kg_co2eq` becomes `None`, but `DataEntryEmissionService.upsert_by_data_entry` deletes emission rows when `prepare_create` returns no computations (i.e., factor dropped / miss). To match actual behavior (and your plan doc’s clarification), document this as “emission rows are deleted / no emissions exist for the entry” rather than persisting a `kg_co2eq=NULL` row.

---

### File: `backend/tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py` (Line 785) — Copilot

## Avoid inline imports inside tests (here `BuildingRoom`). Please move this import to the module top with the other imports to keep import order deterministic and make linting/static analysis simpler.

### File: `backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py` (Line 5) — Copilot

## PR description says “No code changes in this PR yet / plan + reference doc only”, but this PR also adds backend integration tests (new `test_strategy_a_rematch_pg.py` and `test_strategy_b_rematch_pg.py`). Please update the PR description/scope accordingly (or split docs vs tests) so reviewers know to run the Docker-backed test suite.

## Action Items

### Critical: logic, security, correctness

_No critical items — this PR is doc + test-only; the agent's empirical finding (no production code change needed) holds._

### Maintainability / refactoring

- [ ] **`docs/src/implementation-plans/emission-pipeline-flow.md`** — pipeline-flow doc is out of sync with the truths the agent established in the Strategy B plan doc. Three concrete fixes needed in one pass:
  1. Line 140 — move **Buildings — Rooms** from the FK-link row (`data_entry_emissions.primary_factor_id`) to the JSON-link row. Per the agent's empirical finding (PR body) and `BuildingRoomModuleHandler`, rooms uses `primary_factor_id` from `entry.data` with `kind_field='building_name'` / `subkind_field='room_type'` — Strategy A bulk-prefetch covers it. The 1:N emission shape is what's special, not the link location.
  2. Line 164 — the Plan 310-D rematch contract bullet 3 (Strict-drop) says "the entry's `primary_factor_id` is set to `None` and the recomputed `kg_co2eq` is `None`". Replace with: "the entry's emission rows are deleted via `DataEntryEmissionService.upsert_by_data_entry`'s no-emissions branch (which calls `delete_by_data_entry_id`)". This matches the actual code and aligns with `310-d-strategy-b-rematch.md` lines 233-253 ("Strict-drop = delete the entry's emission rows").
  3. Line 154-156 — the list item 1 wraps `year)` onto an unindented line, which breaks list rendering in CommonMark. Indent the wrapped text two spaces so it's continuation-of-list-item.

- [ ] **`docs/src/implementation-plans/310-d-strategy-b-rematch.md`** — two doc inconsistencies surfaced after the agent shipped the actual code:
  1. Line 144 — text says "duplication across the 14 test bodies" but the PR shipped 7 (Strategy B file) + 9 (Strategy A file) = 16 ITs. Update count to match what landed.
  2. Line 99 — file path reference says `app/workflows/embodied_energy.py`; the file actually lives at `backend/app/workflows/embodied_energy.py` (the doc convention elsewhere in this file uses the `backend/` prefix). One-line fix.

_Dropped (verification notes):_

- _Copilot's "PR description says no code changes" comment on `test_strategy_a_rematch_pg.py:5` — the PR title was already updated when the agent marked it ready-for-review; this is a PR-description process note, not a code defect._
- _Copilot's "landed in PR #1027" wording on `310-d-strategy-b-rematch.md:13` — #1027 has merged, past tense is now correct._
- _Copilot's "Single bulk-fetch / No per-entry DB roundtrips" comment on `emission-pipeline-flow.md:156` — same reason; #1027 merged, the JSON-link path IS the bulk-fetch path now._
- _Copilot's "inline import of BuildingRoom" on `test_strategy_b_rematch_pg.py:785` — pure nitpick (lint-level polish). Move it whenever you're touching the file next; not worth a dedicated commit._
