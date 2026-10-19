---
status: delivered
issue: 3099
last_updated: 2026-10-19
summary: "After the 2026-10-19 dependency consolidation, make type-check failed: ty 0.0.89 flags narrowed overrides, and vue-tsc 3.3.13 has a template codegen bug. The frontend suites also found no tests, because @playwright/test 1.64 sat next to ct-vue 1.62.1. Fixed in code without pins: backend overrides keep the base type, template closures go, and @playwright/test is dropped so ct-vue is the single Playwright version."
---

# 3099 — type-check and frontend tests after the 2026-10-19 deps update

#3098 and #3049 left `dev` with three independent breakages. The rule for
this fix: change the code, don't pin the tools.

## Backend: ty `invalid-mutable-override` (47)

ty 0.0.89 rejects a subclass that re-annotates a writable attribute with a
narrower type: a write through the base type could then break the subclass.

- **Handler settings** (`kind_field`, `subkind_field`, `category_field`,
  `data_entry_type`, `emission_type`) on `BaseModuleHandler` and
  `BaseFactorHandler` subclasses: drop the subclass annotation, keep the
  value. The attribute keeps the base's declared type. These are plain
  classes, so nothing changes at runtime.
- **Two bare declarations** (`ProfessionalTravelBaseModuleHandler`,
  `_PlannerPurchaseBase`) that narrowed `data_entry_type` without a value
  are gone. `_PlannerPurchaseBase.resolve_computations` now raises
  `ValueError` if the type is missing, instead of trusting the narrowing.
- **`_EquipmentUsageHoursValidationMixin`** now types its two usage-hours
  fields as read-only properties under `TYPE_CHECKING`, mirroring
  `DiscardClientSurfaceMixin`. `EquipmentFactorCreate` can then require
  `int`. Each model still declares the real pydantic fields.

## Frontend: vue-tsc 3.3.13 (14)

vuejs/language-tools#6237 (open) appends `.value` to an imported object
read inside a template arrow function. #3051 pinned vue-tsc 3.3.11 to dodge
it; this fix removes the closures instead, and with them the dependabot
ignore for 3.3.12.

- Upload cards already emit their own `TargetType`. `ModuleUploadsSection`,
  `SubmoduleItem` and `ReductionObjectivesSection` now bind
  `@upload="openDataEntryDialog"` and no longer restate it.
- `ModuleSelector.toggleState` takes the state key and looks it up itself.
- With the bug out of the way, the codegen also checks `ModuleTable` props.
  `SubModuleSection` passed `submodule.id` (`string`). It now passes
  `submodule.type`, which is the same value in every config, planner
  included. The Buildings branch of `ConditionalSubmoduleProps` now uses
  `AllSubmoduleTypes`, like every sibling.

## Frontend tests: two Playwright copies

#3075 moved `@playwright/test` to 1.64. `@playwright/experimental-ct-vue`
has no stable release past 1.62.1 and pins `playwright` exactly, so two
copies loaded and both suites reported "No tests found".

`@playwright/test` is only `module.exports = require('playwright/test')`.
It is removed: specs and `playwright.config.js` import `playwright/test`,
and `playwright` arrives through ct-vue. The `playwright` command comes
from ct-vue too. ct-vue is now the only Playwright version, together with
the CI image tag. **Don't add `@playwright/test` or `playwright` back as a
direct dependency**: that brings the second copy back. #3100 tracks whether
experimental CT is still the right base.

## Also

The stray root dependency `"i": "^0.3.7"`, added by #3049 and used
nowhere, is removed.

## Verification

- `make type-check` and `make lint`: pass.
- Backend `make test`: 3137 passed, 77% coverage.
- Frontend `npm run test-ct`: 873 passed. `npm run test:e2e` after a fresh
  `quasar build`: 102 passed, 5 skipped.
