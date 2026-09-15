---
status: delivered
issue: 2699
last_updated: 2026-09-15
summary: 'The Headcount student form ("Add student FTE") rendered the raw key headcount-student-form-subtitle: the subtitle text was removed from the translations on 2026-07-07 but the submodule config still had hasFormSubtitle: true. The flag is now off; the form has no subtitle.'
---

# Headcount — student form subtitle shows the raw key (#2699)

## Problem

Under the "Ajouter un EPT étudiant·e" form of the Headcount module, the
subtitle line shows the literal string `headcount-student-form-subtitle`
instead of text.

`ModuleForm.vue` renders `$t('<module>-<submodule>-form-subtitle')` whenever
the submodule config sets `hasFormSubtitle: true`. The Headcount `student`
submodule (`frontend/src/constant/module-config/headcount.ts`) still had the
flag on, but the translation entry was deleted on 2026-07-07 in
`ee0fe8f2b feat: amend many translations` (it read "Enter the aggregated
student FTE for your unit over the year."). The key was not renamed, as first
assumed in the issue thread — it no longer exists in any i18n file, so
vue-i18n falls back to the key itself.

## Decision

Turn `hasFormSubtitle` off for the Headcount student submodule. The text was
removed deliberately; the single-field form ("Total student FTE") is
self-explanatory and the title tooltip already carries the explanation.
No other submodule uses a form subtitle, so no i18n entry is added.

If a subtitle is wanted again later, add the
`headcount-student-form-subtitle` entry in `frontend/src/i18n/headcount.ts`
and flip the flag back on — both must change together.

## Cleanup done in the same PR

While checking whether the subtitle text survived under another key, five
entries in `frontend/src/i18n/headcount.ts` turned out to be referenced by
nothing (neither a literal `$t('…')` nor the `${moduleType}-${submoduleType}-…`
templates in `ModuleForm.vue` / `SubModuleSection.vue`). They were removed:

- `headcount-student-table-title-info-label`
- `headcount-charts-no-data-message`
- `headcount-student-form-add-button` (the student submodule uses
  `addButtonLabelKey: 'common_update_button'`)
- `headcount-student-form-title-info-label` (the form tooltip reads
  `module-headcount-submodule-student-form`)
- `headcount-member-function-required` (validation uses `validation_required`)

## Files

- `frontend/src/constant/module-config/headcount.ts` — `hasFormSubtitle: false`.
- `frontend/src/i18n/headcount.ts` — five unused entries removed.
