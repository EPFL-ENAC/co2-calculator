---
status: delivered
issue: 1558
last_updated: 2026-07-08
title: "Issue 1558 — Calculator year selector doesn't show a newly-opened year until a hard refresh"
summary: "yearConfigStore.configuredYears (which years are open to users) was hydrated once at auth bootstrap and only ever refetched when still empty, so a year opened via the backoffice mid-session stayed invisible in the calculator's year dropdown — and could keep a user bounced to /unauthorized — until a hard reload rebuilt Pinia state from scratch. workspaceStore.units/getUnitResults were both ruled out as unrelated to this specific bug."
---

# Issue 1558 — Calculator year selector doesn't show a newly-opened year until a hard refresh

## Problem (as confirmed)

Original report: after finishing a data upload, the "Ouvrir l'année pour les utilisateurs" button stays disabled, and the calculator shows no units for that year.

The original hypothesis (a stuck Headcount factor job permanently blocking the backend's `incomplete` flag) was ruled out by the repo owner's own reproduction:

> "I've reproduced it. It's not a login/logout problem, it's just a store problem. If we refresh the window by hitting Ctrl+R or F5, the new year appears."

## Root cause (confirmed)

The stale piece of state is **`yearConfigStore.configuredYears`**, not `workspaceStore.units`:

- `configuredYears` (`frontend/src/stores/yearConfig.ts`) drives the `startedYears` computed (`configuredYears.filter(is_started)`), which is the **only** input to `WorkspaceSelectorBar.vue`'s year dropdown (`yearOptions`, `workspace-selector/WorkspaceSelectorBar.vue:35-41`) and to `redirectToDefaultRoute.ts`'s landing-route resolution (picks the default year, or redirects to `/unauthorized?reason=no-open-year` when no year is open).
- `configuredYears` is hydrated once by `authStore.bootstrap()` (`GET /session`) and was only ever refetched by two call sites, both gated on `configuredYears.length === 0`:
  - `workspaceGuard.ts`'s `loadWorkspaceFromRoute` (via `fetchStartedYears`-equivalent — it didn't even call it before this fix; see below)
  - `redirectToDefaultRoute.ts`'s `fetchStartedYears()`
  - Since a unit's years list is populated at bootstrap (created-but-unopened years already appear with `is_started: false`), `.length === 0` is essentially never true again after login — so an admin opening a year via the backoffice mid-session never reached these stores until a hard reload re-ran bootstrap from scratch. This exactly matches "F5 fixes it."
- `workspaceStore.units` (org/unit descriptors) has **no year-scoped fields** and doesn't change when a year opens — it was a red herring from the earlier investigation, structurally similar (same fetch-once-if-empty pattern) but not the mechanism behind this specific bug.
- `fetchWorkspaceHome` (`GET workspace/{unit}/{year}/home`) genuinely is fetched fresh on every guard run, as previously assumed — but it only decides content for an *already-selected* unit/year, not which years are offered as selectable in the first place.

**`unitResults` / `getUnitResults()` in `workspace.ts` is confirmed dead code** — a repo-wide grep for `getUnitResults` found it defined and re-exported by the store, but never called anywhere else (no dynamic access, no wrapper). `availableYears` / `currentYearData` / `getLatestYear` on `workspaceStore`, which are all derived from `unitResults`, are dead by extension. Left untouched; out of scope for this fix.

**Backoffice-side (`DataManagementPage.vue`) is not affected by this bug.** Its year dropdown reads `yearConfigStore.availableYears`, a *static* `ref` populated once with the range `2023..currentYear` (not fetched from the backend at all — see the `TODO` at `yearConfig.ts:185-186`), so there's no cache to go stale there.

## Fix (delivered)

Both call sites now refetch `configuredYears` **unconditionally** instead of only when empty — mirroring how `fetchWorkspaceHome` already refreshes on every guard run:

- `frontend/src/router/guards/workspaceGuard.ts` — `loadWorkspaceFromRoute` now calls `useYearConfigStore().fetchConfiguredYears()` unconditionally on every run (which only happens on unit/year param changes or first entry into the workspace section, per the outer `workspaceGuard`'s existing short-circuit — so this doesn't add a fetch on every module/tab navigation, only on the transitions where staleness could actually matter).
- `frontend/src/router/guards/redirectToDefaultRoute.ts` — `fetchStartedYears()` now calls `fetchConfiguredYears()` unconditionally as well, so the parameterless landing route (and its no-open-year redirect) also reflects current backend state.
- `workspaceStore.units`'s own fetch-once-if-empty guard was deliberately left untouched — it's unrelated to this bug and touching it would be an unjustified, unrequested behavior change.
- Added `data-testid="workspace-unit-select"` / `data-testid="workspace-year-select"` to `WorkspaceSelectorBar.vue`'s two `q-select`s for stable test targeting.

## Regression test (delivered)

`frontend/tests/integration/workspace-year-refresh.spec.ts` (+ `frontend/tests/integration/setup/workspace-year-refresh-mocks.ts`), following the existing `data-management.spec.ts` / `simulator-mocks.ts` HTTP-mocking conventions:

- Mocks a session with two units and a `year-configuration/` list where year 2025 exists but is closed (`is_started: false`).
- Loads the calculator (`GET /en/10-unit-alpha/2024/home`) and confirms the year dropdown offers only 2024.
- Flips the mocked `year-configuration/` response so 2025 is now open (simulating the backoffice action happening in another tab/session).
- Triggers an **in-app navigation** (no reload) by switching units via the `WorkspaceSelectorBar` unit dropdown — the smallest realistic action that changes the route's `:unit` param and re-runs the workspace guard.
- Asserts 2025 now appears in the year dropdown, and that the `year-configuration/` request count increased after the navigation.
- Verified this test fails (times out waiting for "2025" in the dropdown) when the fix is reverted, and passes with it applied — confirming it would have caught the original bug.

## Verification

- `vue-tsc --noEmit -p tsconfig.typecheck.json` — clean.
- `eslint` on all touched source files — clean (test files are globally ignored by `eslint.config.js`, consistent with the rest of `tests/integration/`).
- `prettier --check` on all touched files — clean.
- `npx playwright test tests/integration/workspace-year-refresh.spec.ts` — passes with the fix, fails without it (verified both ways).

## Steps (historical)

- [x] Do not build on the old Headcount-job hypothesis.
- [x] Reproduce precisely by tracing code paths (no live backend in this environment): confirmed the symptom is the year dropdown in `WorkspaceSelectorBar.vue` not offering a newly-opened year, and separately that a user with no other open year can get stuck on `/unauthorized?reason=no-open-year` — both driven by the same stale `configuredYears` state.
- [x] Traced the mechanism to `yearConfigStore.configuredYears` / `startedYears`, not `workspaceStore.units`. Resolved `unitResults`/`getUnitResults()` as dead code.
- [x] Fixed by unconditional refetch in both call sites (workspace guard + landing resolver).
- [x] Added a Playwright regression test exercising the in-app-navigation path, verified red/green.
- [x] Manual end-to-end verification wasn't possible in this environment (no live backend); verification instead traced the exact code paths a user would hit and confirmed via the regression test's revert/reapply cycle.
