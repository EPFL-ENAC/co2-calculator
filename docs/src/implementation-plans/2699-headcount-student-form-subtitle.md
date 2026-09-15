---
status: delivered
issue: 2699
last_updated: 2026-09-15
summary: 'The Headcount student form ("Add student FTE") rendered the raw key headcount-student-form-subtitle: the subtitle text was removed from the translations on 2026-07-07 while the submodule config kept hasFormSubtitle: true. The translation entry is restored so the subtitle shows real text again.'
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

Restore the `headcount-student-form-subtitle` entry in
`frontend/src/i18n/headcount.ts` with the text that existed before
2026-07-07 (EN "Enter the aggregated student FTE for your unit over the
year.", FR "Entrez de manière agrégée les EPT des étudiant·es qui ont
travaillé dans votre unité sur l’année."). The config flag stays on. The
maintainers want a visible subtitle under the form title, not its removal.

`hasFormSubtitle` and the `<module>-<submodule>-form-subtitle` entry must
change together; the Headcount student submodule is the only one using it.

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

- `frontend/src/i18n/headcount.ts` — subtitle entry restored, five unused
  entries removed.
