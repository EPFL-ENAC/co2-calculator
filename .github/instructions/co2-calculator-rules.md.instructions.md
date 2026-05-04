---
description: follow these guidelines for backend and frontend development to ensure code quality, type safety, and architectural consistency.
applyTo: "backend/**, frontend/**"
---

You are a senior software engineer. Follow ALL rules strictly. No explanations unless asked. Output production-ready code only.

# RTK — Token-Optimized CLI

**SUPER IMPORTANT**: Always prefix shell commands with `rtk` to save 60-90% tokens.

## Rule

- ALL shell commands MUST use `rtk` prefix
- Examples:
  - `rtk git status` (not `git status`)
  - `rtk npm run lint` (not `npm run lint`)
  - `rtk pytest` (not `pytest`)
  - `rtk wc -l file.vue` (not `wc -l file.vue`)

## Meta commands

- `rtk gain` - Token savings dashboard
- `rtk gain --history` - Per-command savings history
- `rtk discover` - Find missed rtk opportunities

# COMMUNICATION

- Always respond in English.
- Keep answers concise and direct.
- Prioritize action over long theory.
- When asked "why", explain concrete runtime impact in the app.
- Use clear, practical wording (no fluff).

# DEFAULT WORKING STYLE

- Investigate end-to-end flow before coding (frontend composables, API, backend compute path, chart rendering).
- Fix root cause, not only symptoms.
- Prefer implementing directly after analysis (unless a plan is explicitly requested).
- Preserve existing user changes in the working tree; never reset unrelated work.
- Reuse existing patterns used in similar modules (for example, behavior already used in travel-like dynamic forms).

# IMPLEMENTATION PLANS

- All implementation plans (whether produced by Claude, Copilot, or any other agent) MUST be saved under `docs/implementation-plans/` at the repository root.
- File naming convention: `[issue-id]-[short-kebab-description].md` where `[issue-id]` is the integer GitHub issue id (regex: `^[0-9]+-[a-z0-9-]+\.md$`).
  - Examples: `840-root-level-rollup-emission-rows.md`, `252-chart-results-endpoint.md`.
- One plan file per issue scope; if an issue spawns multiple sub-plans, suffix with a discriminator (e.g., `859-seed-1-factors-ingestion.md`, `859-seed-2-data-entries-ingestion.md`).
- Do not write plans into the working directory, `backend/`, `frontend/`, or scratch locations — always under `docs/implementation-plans/`.
- If no GitHub issue exists for the work, create one first or ask the user for the id before writing the plan.

# DATA AND UI CONSISTENCY RULES

- Form values, table values, and chart values must stay consistent after create/update.
- New entries should update visible charts without requiring page leave/re-enter.
- Tree/summary charts should render when data exists, even in non-finalized states when business rules allow.
- Validate both empty-state and partial-data-state behavior.
- Ensure color usage follows the existing design system and shade progression.

# DEBUGGING AND VALIDATION

- Reproduce the issue first, then patch.
- When a bug spans frontend and backend, validate both request payload and server response.
- For API errors (400/500), verify payload shape and keep error handling readable.
- Run relevant local checks after edits (targeted type-check/lint/tests when feasible).
- Verify changes on the exact screens involved, including selector changes and refresh/navigation behavior.

# CODE QUALITY

- Keep changes focused and minimal for the requested fix.
- Favor readability over clever abstractions.
- Add short comments only where intent is non-obvious.
- Keep naming aligned with domain language (room type, factor, module, category, etc.).
- Avoid introducing new patterns/styles in the same file; follow existing local conventions.
- Do not use inline imports in Python. They are considered bad code smell, reduce readability, and can hide circular dependencies. Always import at the top of the file.

# FORMATTING RULES

- Always run the project formatter/lint autofix for touched files before finalizing.
- Keep import ordering consistent with project conventions; remove unused imports immediately.
- Prefer small, readable functions over long blocks; extract helpers when logic becomes dense.
- Keep line length readable and avoid deeply nested conditionals when a guard clause is clearer.
- Keep naming and casing consistent with existing code in each layer (`camelCase` in TS, `snake_case` in Python).
- Do not introduce new formatting styles in the same file; follow the existing local style.

# BACKEND — Python 3.12 (uv & Makefile)

- **Tooling**: Use `uv` for dependency management and environment execution. All common tasks (lint, test, run) must be executed via `Makefile` commands.
- **Ruff**: line-length=88, indent=4, select=["E","F","I"], double quotes, fix=true, exclude migrations.
- **Mypy**: strict mode — all public functions must have full type annotations. No `Any` unless unavoidable. `warn_unused_ignores=true`.
- **Alembic**: Use for all database schema changes. No direct SQL schema edits. Keep migrations focused and reversible. Only use `revision` and `upgrade` commands; avoid manual edits to migration files unless necessary for complex operations: INDEX ARE CODE FIRST, alembic second.
- **SQLAlchemy**: Always wrap column references in `col()` (e.g., `col(Model.field) == value`) to satisfy Mypy `ColumnElement` types.
- **Docstrings**: Google-style docstrings mandatory for all public functions/classes.
- **Structure**: Imports: stdlib → third-party → local (alphabetical). Functions ≤40 lines, single responsibility, ≤2 levels nesting.
- **Error Handling**: Explicit exceptions only; no bare `except`.
- **Endpoints**: Prefer extending existing generic endpoints over introducing narrowly scoped new endpoints.
- **Schemas**: Keep APIs and schemas generic when possible; avoid app-specific special cases unless required.
- **Derived values**: Avoid storing derived or redundant values in entries when they can be resolved from factors/lookups.
- **Fallback categories**: Avoid ambiguous fallback categories (for example "misc") unless explicitly required by product rules.
- **Legacy logic**: Remove legacy logic when replacement is validated (do not keep dead dual paths).
- **No backward compatibility**: Do not maintain backward compatibility for deprecated columns, APIs, or patterns. When introducing new approaches, remove old ones immediately.
  UNLESS explicitly required for a migration path, in which case clearly document the migration steps and timelines.
- **Source of truth**: Backend is the single source of truth for data manipulation and business transformations.
- **Factor resolution**: Keep factor resolution logic centralized to avoid divergence across modules.
- **Silent fallbacks**: Avoid silent fallbacks that hide data issues; surface missing mappings/factors clearly.
- **Module cohesion**: Keep module logic cohesive — ingestion, lookup, calculation, and serialization should each have clear boundaries.
- **Comments**: 1-2 lines by default, up to 4 lines only for complex domain logic. Explain intent/constraints, not obvious implementation steps.
- **Testing**: Validate with realistic fixtures covering no-data, partial-data, and multi-category scenarios.

# FRONTEND — Vue 3 + TypeScript + Quasar

- **Script**: `<script setup lang="ts">` only. Composition API mandatory (No Options API).
- **Style**: Prettier (singleQuote=true, semi=true). ESLint (vue/flat/recommended + vueTsConfigs.recommended).
- **Types**: `defineProps`/`defineEmits` with explicit interface types; no implicit `any`.
- **Error Handling**: Never use `any` for catch error parameters. Use `unknown` and narrow with `instanceof Error` or type guards.
- **Unused Variables**: Remove unused imports and variables (e.g., unused Quasar `$q` injection).
- **Logic**: No business logic in templates; extract to Composables (`useX`). Keep business calculations in composables/store logic, not in presentational chart components.
- **Composables**: Prefer module/domain-specific composables instead of overloading unrelated shared composables.
- **Legacy logic**: Remove legacy logic when replacement is validated (do not keep dead dual paths).
- **State**: Pinia (strongly typed).
- **Component Size (SUPER IMPORTANT)**: Components ≤500 lines (hard limit).
  - When approaching 400 lines: PLAN refactoring immediately
  - When exceeding 500 lines: VIOLATION - must split
  - Extraction strategies:
    - Extract reusable UI patterns → `components/molecules/`
    - Extract feature-specific compositions → `components/organisms/`
    - Extract business logic → `composables/useX.ts`
    - Extract complex templates → sub-components
  - Examples from this codebase:
    - ModuleConfig refactored to extract UploadCard components
    - useUploadCard composable extracted shared logic
- **Cleanliness**: No `console.log`, no unused variables.
- **Reactivity**: Ensure selector-driven defaults refresh reactively when dependencies change (module, room, room type, heating type, factor). Avoid duplicating option-loading logic across modules. Ensure dependent form fields update immediately when source selectors change (room, room type, heating type, etc.).
- **UI continuity**: Preserve UI state after create/update — no disappearing charts, no forced navigation to refresh data. Avoid flicker and stale values in reactive UI updates.
- **Consistency**: Keep table, form, and chart transformations aligned to the same source of truth. Use deterministic category ordering and stable keys to avoid chart flicker/re-mount issues. Keep chart/category behavior deterministic and consistent with visible/available data. Keep display values rounded/normalized where users compare form/table/chart output.
- **i18n**: Keep labels synchronized with domain fields; avoid hardcoded user-facing strings in components.
- **States**: Prefer explicit loading/empty/error states over silent failures in visual components.
- **Validation**: Validate behavior for initial load, first entry, edit, refresh, and navigation back to page.

# ARCHITECTURE & WORKFLOW

- **Clean Architecture**: Strict separation of `domain` / `application` / `infrastructure`.
- **Dependency Management**: Update `pyproject.toml` using `uv add` or `uv remove`.
- **Clean Code**: No circular imports, no dead code, no commented-out code, no `TODO`s.
- **Automation**: If a task can be done via `make` (e.g., `make lint`, `make test`), use it.

# TESTING

- **Backend**: `pytest` with fixtures. Mock all external services. No real DB in unit tests.
- **Frontend**: `Vitest` for composables and business logic; separate from UI components.

# COMPONENT SIZE ENFORCEMENT

## Why

- Maintainability: Smaller components are easier to understand and modify
- Testability: Easier to write focused unit tests
- Reusability: Small components can be reused across features
- Performance: Better tree-shaking and code splitting

## Enforcement

- **Warning**: Components >500 lines trigger pre-commit warning (see `scripts/pre-commit-hook.sh`)
- **Action Required**: Refactor when approaching 400 lines
- **Exceptions**: Chart components may exceed limit if justified (document in comment)

## How to Split

1. **Identify concerns**: UI rendering, business logic, data fetching
2. **Extract logic**: Move to composables (`useX.ts`)
3. **Extract UI**: Move reusable patterns to molecules
4. **Split templates**: Break large templates into sub-components
5. **Use composition**: Compose small components instead of one large component

## Current Technical Debt

See GitHub issue for list of components exceeding 500 lines requiring refactoring.

# NEVER

- Ignore lint/type errors or use `# type: ignore` without a specific error code (e.g., `# type: ignore[import]`).
- Use bare column comparisons in SQLAlchemy joins—always use `col()`.
- Guess missing types; if a type is unknown, investigate the library or define a Protocol.
- Mix quote styles or leave unused imports.
