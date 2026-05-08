# Bot Review TODOs: PR #1050

## Source Branch: `feat/310c-runner-cutover`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 21 out of 21 changed files in this pull request and generated 1 comment.

---

### File: `backend/app/tasks/bootstrap.py` (Line 40) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.tasks.ingestion_tasks](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/644)

### File: `backend/app/tasks/bootstrap.py` (Line 42) — github-advanced-security[bot]

## CodeQL / Unused global variable

The global variable '\_BOOTSTRAPPED' is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/643)

### File: `backend/app/tasks/ingestion_tasks.py` (Line 31) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.tasks.runner](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/645)

### File: `backend/app/tasks/runner.py` (Line 98) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.tasks.bootstrap](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/646)

### File: `backend/app/tasks/ingestion_tasks.py` (Line 153) — Copilot

`_run_ingest` calls `provider.ingest()` even though providers currently update the job to `state=FINISHED` (and commit) internally. Because `DataIngestionRepository.update_ingestion_job()` auto-stamps `finished_at` on the _first_ transition to FINISHED, this can set `finished_at` (and expose FINISHED to SSE/UI) before the runner’s preemption check + `data_session.commit()` and before `factor_ingest` chains child jobs. Please prevent providers from writing `state=FINISHED` when invoked via `run_job` (keep them on RUNNING/progress updates only), and let the runner perform the single authoritative FINISHED transition so `finished_at` and pipeline semantics stay accurate.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/tasks/ingestion_tasks.py` — providers race the runner on the FINISHED transition.** The shared `_run_ingest` calls `provider.ingest()` which internally fires `provider._update_job(state=FINISHED, …)` and commits _before_ returning. Because PR #1026 made `finished_at` auto-stamp on the first FINISHED transition, this means: (a) `finished_at` is stamped at provider time, not after the runner's `data_session.commit()` — the duration metric measures provider work only, omits any handler-side post-processing; (b) `factor_ingest`'s post-success `_chain_recalc_for_stale` runs AFTER the parent is already FINISHED, so the dashboard briefly sees a FINISHED parent with no children; (c) the runner's preempt-check is bypassed — if a stale-sweep preempted us mid-handler, we'd already have written FINISHED before the check could roll back. **Fix**: thread a `defer_finalize: bool = False` flag through the provider constructor (or detect "called via run_job" by presence of an injected callable) and have `_update_job` skip the state write when set. Runner-driven path passes `defer_finalize=True`; legacy callers (none after this PR, but for safety) keep the old behavior. Then `_run_ingest` drops the comment-flagged "duplicate is harmless" wishful thinking. The bot's diagnosis is correct; the in-code comment at lines 148-153 acknowledges the issue but defers it as "Plan-D scope" — promote to in-this-PR scope since it now demonstrably breaks the FINISHED contract.

### Maintainability / refactoring

- [ ] **`backend/app/tasks/{bootstrap.py, ingestion_tasks.py, runner.py}` — three CodeQL "Cyclic import" alerts (#644/#645/#646) flag one underlying cycle.** The graph is `ingestion_tasks` (top-level: `from app.tasks.runner import chain_job`) → `runner` (lazy in `run_job`: `from app.tasks.bootstrap import bootstrap_handlers`) → `bootstrap` (lazy in `bootstrap_handlers`: `from app.tasks import ingestion_tasks`). Runtime is safe because the back-edges are inside function bodies (lazy), but CodeQL analyzes function bodies too and reports the static cycle. **Fix**: extract `chain_job` (and any helper it pulls in) into `backend/app/tasks/_chain.py`. Then `ingestion_tasks` imports from `_chain` (no cycle), `_chain` imports `run_job` lazily from `runner` (lazy is fine since `chain_job` only calls `run_job` from within its function body via `fire_and_forget`), and `bootstrap` only needs to import the handler modules. The cycle goes away and CodeQL clears all three alerts. Avoid the easy `# codeql[py/cyclic-import]` suppression; the cycle is a real architecture smell that complicates onboarding even if it's runtime-safe.

_Dropped (CodeQL false positive): "Unused global variable `_BOOTSTRAPPED`" on `bootstrap.py:42`. The variable IS used — read on line 34 and written on line 42. CodeQL's stub here doesn't see the `global _BOOTSTRAPPED` declaration as making the read meaningful. Verified by `grep -n _BOOTSTRAPPED bootstrap.py` showing the read inside `bootstrap_handlers`._
