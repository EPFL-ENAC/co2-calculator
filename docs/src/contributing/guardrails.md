---
status: delivered
last_updated: 2026-07-16
summary: Engineering guardrails for maintainers shipping releases without the lead — architecture invariants, style rules, and what not to touch.
description: Engineering guardrails — architecture invariants, style rules, and workflow for backend and frontend development.
applyTo: "backend/**, frontend/**"
---

# Engineering Guardrails

Read this before your first PR, and again before every release. It exists so
that releases shipped while the lead is away stay coherent with the
architecture and philosophy of this codebase. When this page and your
instinct disagree, this page wins. When this page and the code disagree, see
the [source-of-truth hierarchy](../llm-agent-guide.md).

## Before you code

1. **Find the plan.** Every subsystem is documented by its implementation
   plans: grep [`implementation-plans/`](../implementation-plans/) for the
   issue number or module name and read what shipped. This is the single
   highest-leverage habit in this repo.
2. **No plan for your issue? Write one first.** Every issue ends with a
   delivered plan file in `implementation-plans/` — even small fixes get a
   short one, backfilled at worst. If your PR diverges from its plan, update
   the plan in the same PR. Plan files are named
   `<issue-id>-<kebab-slug>.md` with `status`/`issue`/`last_updated`/`summary`
   frontmatter (see the [LLM agent guide](../llm-agent-guide.md)); abandoned
   plans move to `implementation-plans/archive/`. Their location is settled
   (#860) — do not propose moving plans out of `docs/src/`. Bot-review
   feedback and code-review notes live in `docs/code-review/`, not with the
   plans.
3. **Mirror, don't invent.** New modules copy the travel-like dynamic-form
   shape; new endpoints copy a neighboring router. A new pattern needs a
   written reason (ADR) the existing one can't give. Do not introduce new
   patterns while the lead is away.

## Architecture invariants

These are not preferences; they are load-bearing.

- **Backend is the single source of truth.** Every formula, aggregation, and
  transform lives server-side. The frontend renders backend output — never
  reimplement a computation client-side. Two implementations of a carbon
  formula will drift, and a drifted published number is the worst failure
  this project can have. Keep factor resolution centralized, and don't store
  derived values in entries when they resolve from factors/lookups.
- **Respect the layering — no SQL in routes.** The call chain is
  `route → service → repo`, or `route → workflow → service → repo` for
  multi-step operations. Repos own the SQL, services own the logic, routes
  own the transaction: **the commit happens in the route**, never in a
  service or repo. This hierarchy is non-negotiable.
- **No silent fallbacks.** No "misc" buckets, no swallowed exceptions, no
  defaulted-away missing data. A wrong total that _looks_ complete is worse
  than a visible error. Fail hard: `raise`, don't `logger.error` and carry
  on — a log line nobody reads is a silent fallback.
- **Frontend never checks roles.** UI gates on dedicated permission keys
  (e.g. `module.btn.validated/{cf}`); the backend decides what a role means.
  Authorization fails closed. Boot-time config checks live in the FastAPI
  lifespan, not in `Settings` validators.
- **The DB persists across deploys.** Data migrations ship in the same PR as
  the code change. Never hand-author Alembic migrations — use
  `make db-revision`, then prune false-positive `drop_index` calls. Keep
  manual edits to the generated migration to a strict minimum — anything
  expressible in model code belongs in model code.
- **The pipeline stays idempotent.** Ingestion and recompute must be safely
  re-runnable. Before changing anything under `backend/app/workflows/` or
  recalculation, read the 310-series plans and the stuck-job fix plans
  (1215, 1219, 1559, 1723).
- **No backward-compatibility paths.** When the new way ships, delete the
  old way in the same PR. No dual-path bloat.

## Performance budget

- An endpoint answers in **< 80 ms locally**. The dev platform's DB is ~4×
  slower than local, so 400 ms local becomes 1600 ms in dev. The real goal:
  **page response < 400 ms in dev**, which means a page's combined calls
  stay near 100 ms locally.
- Minimize XHR calls per page — extend an existing endpoint or batch before
  adding a new call.

## Frontend rules

- Follow the existing CSS architecture — extend what's in
  `frontend/src/css/`, never add a parallel styling approach.
- Icons are SVG. Do not add icon fonts.
- All HTTP goes through the centralized ky client
  (`frontend/src/api/http.ts`), via a module file in `frontend/src/api/` —
  never `fetch`, axios, or raw ky from a component.
- Layout lives in `pages/`, logic lives in `components/` built for reuse.
  Don't wire a route straight to a one-off component — the page composes,
  the components carry the logic.
- Minimize layers: no new wrappers, stores, or indirection a page can do
  without. Shared state that must exist goes in Pinia, strongly typed.
- Form, table, and chart values stay consistent — same backend source,
  stable keys and deterministic ordering. Creating or editing an entry
  updates visible charts without leaving the page.
- No hardcoded user-facing strings — every label goes through i18n.
- Visual components show explicit loading/empty/error states — never a
  silent blank.

## Style rules

- Python: functions ≤40 lines, ≤2 nesting levels, single responsibility.
  Imports at top of file, never inline. No `assert` for runtime narrowing —
  use `if x is None: raise ValueError(...)`.
- SQLModel: wrap column refs in `col()`; import `func`/`case`/`or_`/`asc`
  from `sqlmodel` when re-exported there, not from `sqlalchemy`.
- No type suppressions — no `# type: ignore`, no `@ts-expect-error` /
  `@ts-ignore`. Fix the types instead. In the rare case one is truly
  unavoidable, it carries the specific error code (`[arg-type]`) and a
  one-line reason.
- TypeScript: `catch (e: unknown)`, narrow with `instanceof Error`. Vue
  components hard-capped at 500 lines — extract composables at 400.
- No defensive programming: no guards for states the types make impossible.
- Comments explain intent (why), not implementation (what); 1–2 lines.

## Workflow

- PRs target `dev`. Releases flow `dev` → `stage` → `main`. Never delete or
  force-push `dev`, `stage`, or `main`.
- Pipeline-related work merges into `fix/pipeline-debug`, not `dev`, until
  the lead says otherwise.
- `make ci` (lint + type-check: ruff + ty on backend, vue-tsc on frontend)
  must pass locally before pushing. A plain `tsc` pass is not sufficient —
  run `make type-check` or the commit hook will block.
- Backend dependencies change via `uv add` / `uv remove`, never by
  hand-editing `pyproject.toml`.
- **Every bug fix ships with a regression test** that fails without the fix,
  and every change ships with a test on the side it touches. Backend tests
  run via `uv run pytest`. Frontend tests are Playwright: component tests in
  `frontend/tests/unit` (`npm run test-ct`), integration tests in
  `frontend/tests/integration` (`npm run test:e2e`).

## While the lead is away

- **Ship small.** Several small releases beat one big one; a small release
  is one you can revert.
- **Do not touch without a written plan reviewed by both maintainers:**
  recalculation/pipeline internals, permission scoping, anything that
  migrates validated emission data.
- **Defer, don't improvise:** architecture changes, new dependencies, new
  patterns, and schema changes to validated data wait for the lead. Park
  them as issues with your proposal written up.
- **When in doubt, apply the invariant that generalizes:** no silent
  fallbacks. Making the uncertainty visible — a loud error, a blocked PR, a
  question in the issue — is always the right call.
