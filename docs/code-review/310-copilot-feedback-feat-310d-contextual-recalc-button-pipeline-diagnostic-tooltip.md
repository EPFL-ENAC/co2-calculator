# Bot Review TODOs: PR #1059

## Source Branch: `feat/310d-frontend-recalc-recovery`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Improves the back-office data-management module header UX for Plan 310‑D by (1) making the manual recalculation button appear only when it’s actionable (retry after failure or manual trigger when stale with no active chain) and (2) adding a diagnostic tooltip on the pipeline status badges to surface per-job pipeline state.

**Changes:**

- Adjust recalculation button visibility/label/color to be contextual to pipeline state and failure.
- Add `PipelineDiagnosticTooltip` and render it inside the “Recalculating…” / “Last recalc failed” badges.
- Add i18n keys for the tooltip + retry label and update the 310‑D plan doc.

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated 3 comments.

| File                                                                            | Description                                                                                                                                   |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| frontend/src/i18n/backoffice_data_management.ts                                 | Adds new i18n keys for retry label + pipeline tooltip copy/copy-status + empty-state text.                                                    |
| frontend/src/components/organisms/data-management/ModuleConfig.vue              | Hides recalc button during active pipeline, shows “Retry recalculation” on failure, and mounts the diagnostic tooltip inside pipeline badges. |
| frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue | New tooltip component rendering pipeline id (copy) and per-job state/result/status_message rows from `pipelineStream`.                        |
| docs/src/implementation-plans/310-d-frontend-stale-stats.md                     | Marks plan delivered and documents the contextual button + tooltip decisions.                                                                 |

---

### File: `docs/src/implementation-plans/310-d-frontend-stale-stats.md` (Line 19) — Copilot

The plan is marked `status: delivered`, but the new sections still say “Agreed — to be implemented in the follow-up PR.” Since this PR implements the contextual button + tooltip, update these status lines to reflect that they’re delivered (and ideally reference this PR).

---

### File: `docs/src/implementation-plans/310-d-frontend-stale-stats.md` (Line 93) — Copilot

## This tooltip decision/documentation lists timestamps (`started_at`/`finished_at` formatted relative) and “click for sticky-on-mobile”, but `PipelineDiagnosticTooltip.vue` currently renders neither. Either implement these in the component or adjust the plan so it matches the shipped UI.

### File: `frontend/src/components/organisms/data-management/ModuleConfig.vue` (Line 237) — Copilot

The badge is used as the tooltip anchor but isn’t keyboard-focusable, so keyboard users won’t be able to open the diagnostic tooltip or reach the “copy pipeline id” button inside it. Consider making the anchor focusable (e.g. add `tabindex=0` + appropriate aria label/role, or use a focusable element like a button/icon as the tooltip target) and apply the same treatment to the error badge below.

---

## Action Items

### Critical: logic, security, correctness

_None — all three items are scoped UX / docs polish, not correctness defects._

### Maintainability / refactoring

- [ ] **`docs/src/implementation-plans/310-d-frontend-stale-stats.md` (line ~19 + line ~74)** — both decision sections say "Agreed — to be implemented in the follow-up PR" but the doc's own frontmatter is already `status: delivered` and PR #1059 IS the follow-up. Update both `### Status` lines to "Delivered in PR #1059". Same fix for both sections.
- [ ] **`docs/src/implementation-plans/310-d-frontend-stale-stats.md` (line ~91-93)** — the tooltip decision lists timestamps (`started_at`/`finished_at` formatted relative) and "click for sticky-on-mobile" but `PipelineDiagnosticTooltip.vue` ships neither. Two parts:
  1. **Add timestamps to the component** — they're already in `PipelineJob.started_at` / `PipelineJob.finished_at` from the SSE payload. Render under each job row using a small `formatRelative()` helper (no existing project utility I can find; inline ~10-line implementation is fine).
  2. **Drop "click for sticky-on-mobile" from the plan** — Quasar's `<q-tooltip>` doesn't support click-to-stick natively (would require switching to `<q-popup-proxy>`, which is more invasive and changes the hover UX). Documenting it as a separate future enhancement is honest; trying to pretend the current `<q-tooltip>` does it isn't.

### Accessibility

- [ ] **`ModuleConfig.vue` (lines ~199 + ~213)** — the "Recalculating…" and "Last recalc failed" badges are the tooltip anchors but `<q-badge>` isn't keyboard-focusable by default. Keyboard-only users can't open the tooltip OR reach the copy-pipeline-id button inside it. Fix: add `tabindex="0"` + `:aria-label` to both badges. The `cursor-help` class already signals "interactive" visually; tabindex makes it interactive for assistive tech too. Same treatment on both badge variants since they share the same tooltip slot.
