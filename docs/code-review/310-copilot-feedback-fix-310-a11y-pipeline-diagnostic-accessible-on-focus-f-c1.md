# Bot Review TODOs: PR #1071

Source Branch: `fix/310-a11y-tooltip-focus`
PR Title: fix(310): a11y — pipeline diagnostic accessible on focus [F-C1]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR addresses accessibility finding **F-C1** by making the pipeline diagnostic tooltip reachable for keyboard users when focusing the “Recalculating…” / “Last recalc failed” status badges in the back-office module cards.

**Changes:**

- Expose Quasar `QTooltip`’s `show()` / `hide()` via `defineExpose()` in `PipelineDiagnosticTooltip.vue`.
- Drive tooltip visibility from the parent badges’ `@focus` / `@blur` handlers in `ModuleConfig.vue` using component refs.
- Update the Plan 310-D implementation doc to accurately document the mechanism and the remaining keyboard limitation for the in-tooltip copy button.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated no comments.

| File                                                                            | Description                                                                                                             |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| frontend/src/components/organisms/data-management/ModuleConfig.vue              | Adds tooltip refs and focus/blur handlers to show/hide the diagnostic tooltip from keyboard focus.                      |
| frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue | Adds an internal `q-tooltip` ref and re-exposes `show()` / `hide()` so parents can manually control tooltip visibility. |
| docs/src/implementation-plans/310-d-frontend-stale-stats.md                     | Documents the F-C1 fix mechanism and the explicit limitation around focusing into the tooltip portal.                   |

---
