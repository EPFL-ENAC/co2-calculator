---
status: delivered
issue: 2498
last_updated: 2026-08-28
summary: taxonomy 404 left the research-facilities select silently empty (aria-expanded but zero options, no message) — surface it as a visible load error in the shared kind/subkind composable, and rewrite the stale e2e test that pinned pre-#2391 fallback behaviour
---

# 2498 — research-facilities taxonomy-unavailable dropdown never opens (e2e)

## Root cause

`tests/integration/research-facilities-input.spec.ts`'s "options keep their
acronyms when the taxonomy is unavailable" test was written before #2391 and
pins behaviour that #2391 decision 1 deliberately removed. Before #2391, the
facility list came from a separate `GET factors/{det}/list` catalog endpoint,
independent of the taxonomy — so a taxonomy failure alone left the catalog
still working. #2391 (merged the same day, `57887ce47`) deleted that
endpoint and made the taxonomy the select's **sole** option source
(`docs/src/implementation-plans/2391-factor-option-delivery-rewrite.md`,
decision 1). The mocks file's docstring was updated in that PR to say so;
this one test's assertions were not.

The 8 sibling tests in the same file all use the same `.q-menu .q-item`
selector against the _working_ taxonomy path and pass — ruling out
hypothesis (b) (stale selector / Quasar version bump) outright.

Confirmed empirically (`page.locator('.q-menu').count()` = 0 when the
taxonomy 404s): `useEquipmentClassOptions.ts`'s `loadClassOptions()` catches
the fetch failure and sets `dynamicOptions[classOptionId] = []` — silently
identical to "this submodule genuinely has zero classes". `VirtualSelectField`
(a plain `q-select`) renders no menu at all for an empty option list with no
`no-option` slot: `aria-expanded="true"`, zero `.q-menu` in the DOM, no
message. That is a silent blank, which the guardrails rule out directly ("no
silent fallbacks" / "visual components show explicit … error states — never
a silent blank"), so this is hypothesis (a) — a real bug, in the shared
lookup composable, not resurrecting the deleted catalog endpoint.

## Fix

- `frontend/src/composables/useEquipmentClassOptions.ts`: add `classLoadError`
  (mirrors the existing but previously-unwired `subclassLoadError`), set on
  `loadClassOptions()`'s catch, reset at the start of each load.
- `frontend/src/components/organisms/module/ModuleForm.vue`: destructure it,
  and surface it as the `VirtualSelectField`'s `error`/`error-message` for
  the `kind`/`subkind` branch alongside (not replacing) validation errors
  from `errors[inp.id]`.
- `frontend/src/i18n/common.ts`: new `module_options_load_error` key
  (en-US + fr-CH).
- This is a shared composable both Purchase and Equipment also use for their
  `kind`/`subkind` selects, so the fix applies there too — same failure mode,
  same source.

No new fallback endpoint, no reintroduction of the deleted `/list` catalog —
that would be exactly the dual-path bloat the guardrails rule out.

## Test

Rewrote the failing test:
"a load error, not a silent empty list, shows when the taxonomy is
unavailable" — asserts the error message renders on the field and that
`.q-menu .q-item` stays at 0 (the menu genuinely has nothing to show; the
point is that the failure is now visible, not that options magically
appear). Updated the stale "factor catalog" framing in the test's comment
and in `research-facilities-mocks.ts`'s `taxonomyUnavailable` docstring.

## Deliverables

- [x] `classLoadError` in `useEquipmentClassOptions.ts`
- [x] Wired into `ModuleForm.vue`'s `kind`/`subkind` `VirtualSelectField`
- [x] `module_options_load_error` i18n key (en-US + fr-CH)
- [x] Test rewritten to assert the visible error state
- [x] Full spec file + full component-test suite pass (546/546)
- [x] Flip to `delivered` on merge
