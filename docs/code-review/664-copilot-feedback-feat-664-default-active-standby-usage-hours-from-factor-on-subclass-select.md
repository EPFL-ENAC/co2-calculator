# Bot Review TODOs: PR #1357

## Source Branch: `feat/664-equipments-default-active-and-standby-usage-with-csv-upload`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR implements #664 by extending the equipment class/sub-class selection logic to also seed **usage hours** from factor defaults (in addition to the already-mirrored power/unit fields), while preserving any user-entered values unless the class/sub-class is explicitly changed.

**Changes:**

- Generalizes `useEquipmentClassOptions` to support two categories of factor-populated fields: always-mirrored (`valueFieldIds`) and seed-only-when-empty (`defaultValueFieldIds`).
- Updates `ModuleForm.vue` to configure equipment electric consumption to mirror power fields and default usage-hours fields from the factor on subclass selection.
- Ensures `resetSubclass()` clears both mirrored and defaulted fields so switching class/sub-class re-seeds from the new factor.

### Reviewed changes

Copilot reviewed 2 out of 2 changed files in this pull request and generated 3 comments.

| File                                                    | Description                                                                                                             |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| frontend/src/composables/useEquipmentClassOptions.ts    | Adds configurable lists for always-mirrored vs default-only factor fields; updates factor application + reset behavior. |
| frontend/src/components/organisms/module/ModuleForm.vue | Wires module-specific factor field IDs for equipment usage-hours defaults and power/unit mirroring.                     |

---

### File: `frontend/src/composables/useEquipmentClassOptions.ts` (Line 168) — Copilot

## When copying factor values into the entity, `pf[fieldId]` can be `undefined` if the backend response doesn't include that key. Writing `undefined` into the form state can break validation/serialization and can leave stale values hard to reason about. Prefer coercing missing keys to `null` (or skipping) to keep the entity state consistent.

### File: `frontend/src/composables/useEquipmentClassOptions.ts` (Line 175) — Copilot

## Same issue for default-seeded fields: indexing `pf[fieldId]` can yield `undefined` if the factor response lacks the key. Coerce to `null` (or skip) so the form never ends up with `undefined` values.

### File: `frontend/src/composables/useEquipmentClassOptions.ts` (Line 195) — Copilot

## `resetSubclass()` clears configured fields but doesn't guard against empty/undefined `fieldId` values. Unlike `loadPowerFactor()`, this can attempt to clear `entity['']` if a caller accidentally includes an empty string in `valueFieldIds/defaultValueFieldIds`. Add the same truthy guard for consistency and safety.

## Action Items

### Maintainability / refactoring

- [ ] **frontend/src/composables/useEquipmentClassOptions.ts** (lines 167 & 174) — `pf[fieldId]` is written straight into the form, so a factor response missing a configured key writes `undefined` into entity state (a `required` number field would then read as missing on validate, and serialize oddly). Fix: coerce both writes to `null` — `(entity as any)[fieldId] = pf[fieldId] ?? null;` in the `valueFieldIds` loop and the `defaultValueFieldIds` loop. Defensive only: the live `/values` payload includes all keys and the pre-existing code had the same gap, so no current trigger — but it's a one-token hardening that keeps empty state consistent with init (`null`).

_Dropped: line-195 `resetSubclass` truthy-guard comment — **wrong**. The existing `fieldId in entity` check already prevents touching `entity['']` (`'' in entity` is `false`), and the arrays are built from literal `.push()` calls, so an empty `fieldId` can never enter. No bug; pure consistency nitpick on an impossible case._
