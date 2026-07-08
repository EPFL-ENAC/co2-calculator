---
status: proposed
issue: 1558
last_updated: 2026-07-08
title: "Issue 1558 — Calculator shows no units for a newly-opened year until a hard refresh"
summary: "workspaceStore.units (and possibly other workspace-scoped state) is hydrated once at auth bootstrap and never invalidated, so a year opened via the backoffice stays invisible in the calculator for the rest of the browser session until a hard reload rebuilds all frontend state from scratch."
---

# Issue 1558 — Calculator shows no units for a newly-opened year until a hard refresh

## Problem (revised diagnosis — see below)

Original report: after finishing a data upload, the "Ouvrir l'année pour les utilisateurs" button stays disabled, and the calculator shows no units for that year.

**The original hypothesis in this plan (a stuck Headcount factor job permanently blocking the backend's `incomplete` flag) has been ruled out by the repo owner's own reproduction (2026-07-08):**

> "I've reproduced it. It's not a login/logout problem, it's just a store problem. If we refresh the window by hitting Ctrl+R or F5, the new year appears."

This is decisive: if the backend's completeness computation were genuinely stuck, a page refresh would fetch the same broken state again and the button would stay disabled. Since a hard refresh _fixes_ it, the backend is already correct — the bug is entirely client-side: some piece of frontend state is cached once and never re-fetched, so it silently drifts out of sync with the backend after a backoffice action (e.g. opening the year) changes what should be visible.

## Design (revised)

Investigation so far (needs to be confirmed/completed, not assumed) points at `frontend/src/router/guards/workspaceGuard.ts` and `frontend/src/stores/workspace.ts`:

- `loadWorkspaceFromRoute` (`workspaceGuard.ts:47-70`) only calls `workspaceStore.getUnits()` when `workspaceStore.units.length === 0` — its own comment says why: `"Units are normally hydrated by the auth bootstrap (GET /session); refetch only in the rare case the guard runs before they're available."` Once `units` is populated (once per browser session, at login), it is **never refetched** on subsequent navigation, no matter what changes server-side. This is a textbook stale-in-session-cache pattern that a hard reload (which reinitializes all Pinia state from scratch) would mask exactly the way the owner observed.
- However, `Unit` (`workspace.ts:7-17`) has no year-scoped fields — it's an org/unit descriptor, not "units available for year X." So `units` alone may not be the whole story for "the calculator shows no units for this year" — the actual per-year gating likely lives in `fetchWorkspaceHome` (`GET workspace/{unitId}/{year}/home`, called fresh on every guard run) or in whatever component renders the year-selector dropdown within a unit's workspace.
- A second, currently-unexplained data point: `workspace.ts` also defines `unitResults` / `getUnitResults()` (`GET unit/{id}/results`, populates a `years: YearResult[]` list that drives an `availableYears` computed) — but a repo-wide search found **zero live callers** of `getUnitResults()` outside the store itself. This is either dead code (and irrelevant), or called somewhere this investigation missed (e.g. dynamically, or from a file naming pattern not yet searched) and actually the real mechanism. This must be resolved before concluding what to fix — don't guess.
- `workspaceStore`'s persistence config only persists `selectedParams` to `localStorage` (`workspace.ts:341-346`); `units` and `unitResults` are plain in-memory `ref`s, consistent with "hard refresh fixes it" (a hard reload clears in-memory state and re-triggers the auth-bootstrap fetch; in-SPA navigation does not).

## Steps

- [ ] **Do not build on the old Headcount-job hypothesis** — that work (if any exists on this branch) should be discarded or clearly re-scoped; it was investigating the wrong system.
- [ ] Reproduce first, precisely: open a year via the backoffice "Open year for users" flow in one browser tab/session, then — **without reloading** — navigate to the Calculator for that unit in the same session (e.g. via in-app links/router, not typing a URL that triggers a full navigation) and confirm the year/units are missing. Then hit F5 and confirm they appear. Pin down exactly which piece of UI is wrong when it fails: is it the unit list itself, a year dropdown within an already-selected unit, or something else? The original issue text and the owner's reproduction may be describing slightly different symptoms — resolve this ambiguity with an actual repro before writing code.
- [ ] Trace precisely which store/composable/API response actually drives whatever UI element was confirmed missing in the step above. Confirm or refute the `workspaceStore.units` / `workspaceGuard.ts` hypothesis above. Separately, resolve what `unitResults`/`getUnitResults()` actually is — dead code to ignore, or a real path this investigation missed.
- [ ] Once the actual stale-cache mechanism is confirmed, fix it by adding proper invalidation — the specific mechanism depends on what's found, but candidates: refetch `units` (or whatever the real state is) on every workspace-guard run instead of only when empty; invalidate cached workspace state when returning from the backoffice section of the app; or move the relevant data out of a fetch-once-per-session store into something that's refetched per-navigation (mirroring how `fetchWorkspaceHome` already behaves correctly). Prefer the smallest fix that closes the actual gap — don't refetch everything on every navigation if only one piece of state is the problem.
- [ ] Add a regression test (Playwright integration, following this repo's existing `data-management.spec.ts`-style mocking conventions) that: mocks an initial state where a year/unit is not yet visible, simulates the equivalent of "backend state changed" (update the mocked response), then asserts the relevant frontend state updates on the _next in-app navigation_ without requiring a full page reload — this is the test that would have caught the bug.
- [ ] Manually verify end-to-end if possible: open a year via backoffice, navigate to the calculator via in-app navigation (not a fresh page load), confirm the year/units appear without needing F5.
