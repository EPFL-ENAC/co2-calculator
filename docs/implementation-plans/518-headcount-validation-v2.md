# Implementation Plan: Headcount Data Validation V2 (Issue #518)

This plan covers five distinct changes to the Headcount module, derived from the updated
success criteria in issue #518.

---

## Change 1 — SCIPER uniqueness: error message uses `INSTITUTIONAL_ID_LABEL`

### Context

The DB-level unique constraint (`data_entries_unique_member_uid_per_module_idx`) and the
service-level `check_json_field_unique` exist. The API endpoint needs to call the check and
return an error whose display text comes from the institution-configurable label.

### Backend — `backend/app/api/v1/carbon_report_module.py`

Inside the `create()` endpoint, after `validated_data = handler.validate_create(...)` and
before `DataEntryService(db).create(...)`, add:
Add a thin wrapper to `DataEntryService`:

> `check_json_field_unique` already exists in `data_entry_repo.py`.

### Frontend — error display

Where the API error is caught (the module form submit handler), intercept
`detail.code === "DUPLICATE_INSTITUTIONAL_ID"` and show:
Add i18n key to `frontend/src/i18n/headcount.ts`:

### Files touched

| File                                              | Change                                         |
| ------------------------------------------------- | ---------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`      | Add uniqueness check in `create()`             |
| `backend/app/services/data_entry_service.py`      | Add `check_institutional_id_unique()` wrapper  |
| `frontend/src/i18n/headcount.ts`                  | Add `headcount-member-error-duplicate-uid` key |
| Form submit handler (where 422 errors are caught) | Handle `DUPLICATE_INSTITUTIONAL_ID` code       |

---

## Change 2 — Students total in the FTE-per-position chart (not "Unknown")

### Root cause

`GET /modules/{unit_id}/{year}/headcount/{module_id}` calls:

Student entries (`data_entry_type_id = 2`) have no `position_category` in their JSON, so the
repo resolves `null → "unknown"` (repo line 535).

### Fix — `backend/app/api/v1/carbon_report_module.py`

Replace the single `get_stats` call with two calls:

# 2. Student total FTE as a single "student" bucket

student_total: float = await DataEntryService(db).get_total_per_field(
field_name="fte",
carbon_report_module_id=carbon_report_module_id,
data_entry_type_id=DataEntryTypeEnum.student.value,
)

module_data.stats = {\*\*member_stats, "student": student_total}

### Frontend — `HeadCountBarChart.vue`

The chart already handles `"student"` as a key (line 47 in `colorMap`). The
`te('headcount_student')` guard on line 65 translates it to the i18n label.
No chart change needed; the data change is sufficient.

### Files touched

| File                                          | Change                                               |
| --------------------------------------------- | ---------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`  | Split stats call; merge member stats + student total |
| `backend/app/repositories/data_entry_repo.py` | Add `data_entry_type_id` filter to `get_stats`       |
| `backend/app/services/data_entry_service.py`  | Forward new param to repo                            |

---

## Change 3 — Remove "Student" from position_category dropdown and Members table

### Dropdown

Already done: `headcount.ts` module config lists only 7 options (no `student`).
No further change required.

### Members table — hide rows with `position_category = "student"`

Members imported from CSV could carry `position_category = "student"`. These must not appear
in the Members submodule table.

**Option A (backend filter — preferred):** In `HeadcountMemberModuleHandler`, add a
`default_where` attribute:

```python
class HeadcountMemberModuleHandler(BaseModuleHandler):
    ...
    default_where: list = [
        DataEntry.data["position_category"].as_string() != "student"
    ]
```

In `data_entry_repo.py:get_list_for_submodule`, apply `default_where` conditions before
other filters:

```python
handler_default = getattr(handler, "default_where", [])
if handler_default:
    statement = statement.where(*handler_default)
```

**Option B (frontend filter):** Filter rows whose `position_category === 'student'` inside
the table rendering component before display. This is a simpler change but leaks "student"
members into API responses.

> **Recommended: Option A.** Keeps filtering at the data layer; no student-category members
> ever reach the UI.

### Backend validator

Keep `"student"` in `POSITION_CATEGORY_VALUES` for backward compatibility with existing CSV
data. The filter ensures they are silently excluded from the UI without breaking imports.

### Files touched

| File                                          | Change                                                |
| --------------------------------------------- | ----------------------------------------------------- |
| `backend/app/modules/headcount/schemas.py`    | Add `default_where` to `HeadcountMemberModuleHandler` |
| `backend/app/repositories/data_entry_repo.py` | Apply `default_where` in `get_list_for_submodule`     |

---

## Change 4 — Remove Student Count Helper

### Files to remove

- `frontend/src/components/organisms/module/StudentFTECalculator.vue` — **delete**

### `frontend/src/components/organisms/module/ModuleForm.vue`

1. Remove `import StudentFTECalculator from './StudentFTECalculator.vue'`
2. Remove the `<q-card-section v-if="hasStudentHelper">` block (lines ~31–55)
3. Remove the `onUseCalculatedFTE` function that sets `form['fte']`
4. Remove `hasStudentHelper` from `defineProps` and `withDefaults`

### `frontend/src/constant/moduleConfig.ts`

Remove `hasStudentHelper?: boolean` from `SubmoduleConfig` interface.

### `frontend/src/constant/module-config/headcount.ts`

In the student submodule config, remove `hasStudentHelper: true`.

### `frontend/src/i18n/headcount.ts`

Remove the following keys (no longer referenced):

- `student_helper_title`
- `student_helper_students_label`
- `student_helper_duration_label`
- `student_helper_avg_fte_label`
- `student_helper_calculated_label`
- `student_helper_use_button`
- `` `${MODULES.Headcount}-student-student-helper-title` ``
- `headcount_student_helper_students_error`
- `headcount_student_helper_duration_error`
- `headcount_student_helper_avg_fte_error`

Also update `` `${MODULES.Headcount}-student-form-subtitle` `` to remove the reference to the
calculator helper:

```typescript
[`${MODULES.Headcount}-student-form-subtitle`]: {
  en: 'Enter the aggregated student FTE for your unit over the year.',
  fr: "Entrez l'EPT étudiant agrégé pour votre unité sur l'année.",
},
```

### `frontend/src/components/organisms/module/SubModuleSection.vue`

Remove `:has-student-helper="submodule.hasStudentHelper"` prop binding.

### Files touched

| File                           | Change                                          |
| ------------------------------ | ----------------------------------------------- |
| `StudentFTECalculator.vue`     | **Delete**                                      |
| `ModuleForm.vue`               | Remove import, template block, prop, handler    |
| `SubModuleSection.vue`         | Remove prop binding                             |
| `moduleConfig.ts`              | Remove `hasStudentHelper` from interface        |
| `headcount.ts` (module config) | Remove `hasStudentHelper: true`                 |
| `headcount.ts` (i18n)          | Remove `student_helper_*` keys; update subtitle |

---

## Change 5 — `INSTITUTIONAL_ID_LABEL` documentation (already implemented, record only)

`frontend/src/constant/institutionalId.ts` exports `INSTITUTIONAL_ID_LABEL = 'SCIPER'`.
The i18n key `headcount-member-form-field-user-institutional-id-label` already consumes it.

To reconfigure for another institution, a developer changes only this constant. This is
documented in the file's JSDoc comment.

No additional code change required. Ensure the error message in Change 1 also uses this
constant (handled there).

---

## Execution order

1. **Change 4** — Remove helper (self-contained, frontend only, no dependencies)
2. **Change 3** — Filter student position_category from Members table
3. **Change 2** — Fix student FTE appearing as "Unknown" in chart
4. **Change 1** — SCIPER uniqueness check + error message

---

## Critical files summary

| File                                                                | Changes                                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `backend/app/api/v1/carbon_report_module.py`                        | Uniqueness check (C1), split stats call (C2)                                                      |
| `backend/app/services/data_entry_service.py`                        | `check_institutional_id_unique` (C1), `data_entry_type_id` param (C2)                             |
| `backend/app/repositories/data_entry_repo.py`                       | `data_entry_type_id` filter in `get_stats` (C2), `default_where` in `get_list_for_submodule` (C3) |
| `backend/app/modules/headcount/schemas.py`                          | `default_where` on `HeadcountMemberModuleHandler` (C3)                                            |
| `frontend/src/i18n/headcount.ts`                                    | Duplicate UID error key (C1), remove helper keys (C4)                                             |
| `frontend/src/constant/module-config/headcount.ts`                  | Remove `hasStudentHelper` (C4)                                                                    |
| `frontend/src/constant/moduleConfig.ts`                             | Remove `hasStudentHelper` from interface (C4)                                                     |
| `frontend/src/components/organisms/module/ModuleForm.vue`           | Remove helper block and prop (C4)                                                                 |
| `frontend/src/components/organisms/module/SubModuleSection.vue`     | Remove prop binding (C4)                                                                          |
| `frontend/src/components/organisms/module/StudentFTECalculator.vue` | **Delete** (C4)                                                                                   |
