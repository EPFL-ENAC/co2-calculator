---
applyTo: "**"
---

<!-- Vendored from https://github.com/EPFL-ENAC/it4r-agent-kit @ f6ff6fd
     Do not edit here — edit AGENTS.md upstream, then run `make sync-agent-rules`. -->

# ENAC IT4R — agent operating rules

**This file is the canonical, tool-neutral instruction set** for any AI coding
assistant (Claude Code, OpenCode, Cursor, Codex, …) working on an ENAC IT4R
project. `CLAUDE.md` imports it; `SKILL.md` routes to it. Edit the rules
**here**, once.

These are the rules we found load-bearing across our FastAPI + SQLModel +
Alembic / Vue + Quasar + TypeScript stack. When this file and your instinct
disagree, this file wins. When this file and the project's own rules disagree,
**the project wins** — a consuming repo layers its specifics on top (see
"Adopting this" at the bottom).

## Source-of-truth hierarchy

Read top-down. Lower tiers refine higher tiers, never override them.

1. **Spec / CRD** — scope, mandate, acceptance criteria. Not in the spec, out of scope.
2. **ADRs** — accepted architectural decisions. An accepted ADR binds; a superseded one is history.
3. **Implementation plans** — issue-scoped detail. Check frontmatter `status` before trusting.
4. **Code** — ground truth. Docs and code disagree → code wins, and file a `docs` issue.

## Before you code

1. **Find the plan.** Grep the plans directory for the issue number or module
   name and read what shipped. Highest-leverage habit in any of our repos.
2. **No plan for your issue? Write one first.** Every issue ends with a
   delivered plan file — small fixes get a short one, backfilled at worst. If
   your PR diverges from its plan, update the plan in the same PR. See the
   `plan-conventions` skill for the file shape.
3. **Mirror, don't invent.** New modules copy the shape of an existing module;
   new endpoints copy a neighboring router. A new pattern needs a written
   reason (ADR) the existing one can't give.

## Architecture invariants

Not preferences. Load-bearing.

- **Backend is the single source of truth.** Every formula, aggregation, and
  transform lives server-side. The frontend renders backend output — never
  reimplement a computation client-side. Two implementations drift, and a
  drifted published number is the worst failure a data product can have.
- **Respect the layering — no SQL in routes.** `route → service → repo`, or
  `route → workflow → service → repo` for multi-step operations. Repos own the
  SQL, services own the logic, routes own the transaction: **the commit happens
  in the route**, never in a service or repo.
- **No silent fallbacks.** No "misc" buckets, no swallowed exceptions, no
  defaulted-away missing data. A wrong total that _looks_ complete is worse
  than a visible error. Fail hard: `raise`, don't `logger.error` and carry on —
  a log line nobody reads is a silent fallback.
- **Frontend never checks roles.** UI gates on dedicated permission keys; the
  backend decides what a role means. Authorization fails closed. Boot-time
  config checks live in the app lifespan, not in `Settings` validators.
- **The DB persists across deploys.** Data migrations ship in the same PR as
  the code change. Never hand-author Alembic migrations — generate them, then
  prune false-positive `drop_index` calls. Keep manual edits to a generated
  migration minimal: anything expressible in model code belongs in model code.
- **Background pipelines stay idempotent.** Ingestion and recompute must be
  safely re-runnable.
- **No backward-compatibility paths.** When the new way ships, delete the old
  way in the same PR. No dual-path bloat.

## Performance budget

- An endpoint answers in **< 80 ms locally**. Deployed DBs run several times
  slower than local — measure yours and scale the target accordingly.
- The real goal: **page response < 400 ms in the deployed environment**, which
  means a page's combined calls stay near 100 ms locally.
- Minimize XHR calls per page — extend an existing endpoint or batch before
  adding a new call.

## Frontend rules

- Follow the project's existing CSS architecture — never add a parallel
  styling approach. (For EPFL brand work, use the `epfl-design` skill.)
- Icons are SVG. Do not add icon fonts.
- All HTTP goes through the centralized client, via a module file in `api/` —
  never `fetch`, axios, or raw ky from a component.
- Layout lives in `pages/`, logic lives in `components/` built for reuse. The
  page composes, the components carry the logic.
- Minimize layers: no new wrappers, stores, or indirection a page can do
  without. Shared state that must exist goes in Pinia, strongly typed.
- Form, table, and chart values stay consistent — same backend source, stable
  keys, deterministic ordering. Creating or editing an entry updates visible
  charts without leaving the page.
- No hardcoded user-facing strings — every label goes through i18n, and all
  locale files are updated together.
- Visual components show explicit loading/empty/error states — never a silent
  blank.

## Style rules

- Python: functions ≤40 lines, ≤2 nesting levels, single responsibility.
  Imports at top of file, never inline. No `assert` for runtime narrowing —
  use `if x is None: raise ValueError(...)` (bandit strips asserts under `-O`).
- SQLModel: wrap column refs in `col()`; import `func`/`case`/`or_`/`asc` from
  `sqlmodel` when re-exported there, not from `sqlalchemy`.
- No type suppressions — no `# type: ignore`, no `@ts-expect-error` /
  `@ts-ignore`. Fix the types instead. In the rare case one is truly
  unavoidable, it carries the specific error code and a one-line reason.
- TypeScript: `catch (e: unknown)`, narrow with `instanceof Error`. Vue
  components hard-capped at 500 lines — extract composables at 400.
- No defensive programming: no guards for states the types make impossible.
- Default at the top, `if` guards override it. Avoid `if/else` branching and
  falsy `or` defaults.
- Comments explain intent (why), not implementation (what); 1–2 lines.

## Workflow

- Releases flow `dev` → `stage` → `main`. PRs target `dev`. Never delete or
  force-push a protected branch.
- Conventional commits (`feat:`, `fix:`, …).
- Lint + type-check must pass locally before pushing. A plain `tsc` pass is not
  sufficient for Vue projects — run `vue-tsc`.
- Backend dependencies change via `uv add` / `uv remove`, never by
  hand-editing `pyproject.toml`.
- **Every bug fix ships with a regression test** that fails without the fix,
  and every change ships with a test on the side it touches.
- Ship small. Several small releases beat one big one; a small release is one
  you can revert.
- **When in doubt, apply the invariant that generalizes: no silent fallbacks.**
  Making the uncertainty visible — a loud error, a blocked PR, a question on
  the issue — is always the right call.

## Adopting this in a project

The consuming repo keeps a short local rules file for what is genuinely its
own: commands (`make ci`, `make db-revision`), branch exceptions, perf numbers,
module-specific patterns, and anything situational. It links here for the rest
rather than copying — two rulebooks drift, which is the failure mode this file
exists to prevent.
