# Engineering Guardrails

Read this before your first PR, and again before every release. It exists so
that releases shipped while the lead is away stay coherent with the
architecture and philosophy of this codebase. When this page and your
instinct disagree, this page wins. When this page and the code disagree, see
the [source-of-truth hierarchy](../llm-agent-guide.md).

## Two layers

The **shared ENAC IT4R rules** — architecture invariants (backend is the single
source of truth, `route → service → repo` with the commit in the route, no
silent fallbacks, the frontend never checks roles, no backward-compatibility
paths), style rules, the performance philosophy, and the PR workflow — live in
[`it4r-agent-kit`](https://github.com/EPFL-ENAC/it4r-agent-kit). They apply to
every IT4R project. **Read them first**: [`it4r-rules.md`](./it4r-rules.md) is
a vendored copy of that repo's `AGENTS.md`, imported by `CLAUDE.md`.

Never edit `it4r-rules.md` here — change it upstream in the kit, then run
`make sync-agent-rules`, which re-pulls the file and stamps the commit it came
from in the header. A rule that would be true for any of our projects belongs
upstream; if you find yourself editing the vendored copy, you are editing the
wrong file.

**This page holds only what is specific to co2-calculator.** A rule that would
be true for any of our projects belongs upstream in the kit, not here.

## Before you code

1. **Find the plan.** Every subsystem is documented by its implementation
   plans: grep [`implementation-plans/`](../implementation-plans/) for the
   issue number or module name and read what shipped. This is the single
   highest-leverage habit in this repo.
2. **No plan for your issue? Write one first.** Plan files are named
   `<issue-id>-<kebab-slug>.md` with `status`/`issue`/`last_updated`/`summary`
   frontmatter; abandoned plans move to `implementation-plans/archive/`. Their
   location is settled (#860) — do not propose moving plans out of
   `docs/src/`. Bot-review feedback and code-review notes live in
   `docs/code-review/`, not with the plans.
3. **Mirror, don't invent.** New modules copy the travel-like dynamic-form
   shape; new endpoints copy a neighboring router. Do not introduce new
   patterns while the lead is away.

## co2-specific invariants

- **Keep factor resolution centralized**, and don't store derived values in
  entries when they resolve from factors/lookups. (The general rule this
  refines: the backend is the single source of truth.)
- **The pipeline stays idempotent.** Before changing anything under
  `backend/app/workflows/` or recalculation, read the 310-series plans and the
  stuck-job fix plans (1215, 1219, 1559, 1723).
- **Migrations are generated, never hand-authored** — use `make db-revision`,
  then prune false-positive `drop_index` calls.
- **Permission keys look like `module.btn.validated/{cf}`.** The UI gates on
  those; the backend decides what a role means.
- **Boot-time config checks live in the FastAPI lifespan**, not in `Settings`
  validators.

## Performance budget

- An endpoint answers in **< 80 ms locally**. The dev platform's DB is ~4×
  slower than local, so 400 ms local becomes 1600 ms in dev. The real goal:
  **page response < 400 ms in dev**, which means a page's combined calls
  stay near 100 ms locally.
- Minimize XHR calls per page — extend an existing endpoint or batch before
  adding a new call.

## Frontend specifics

- Extend the CSS architecture in `frontend/src/css/` — never add a parallel
  styling approach.
- All HTTP goes through the centralized ky client
  (`frontend/src/api/http.ts`), via a module file in `frontend/src/api/`.
- i18n lives in `frontend/src/i18n/` — always update **both** `en-US` and
  `fr-CH` locale files together.

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
- **Every bug fix ships with a regression test.** Backend tests run via
  `uv run pytest`. Frontend tests are Playwright: component tests in
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
