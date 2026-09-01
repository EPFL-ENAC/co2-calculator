# Bot Review TODOs: PR #2583
Source Branch: `fix/2401-i18n-in-table`
---
## Raw Feedback
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (copilot-pull-request-reviewer)
Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---
### Summary Feedback (github-advanced-security)

---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 45 out of 47 changed files in this pull request and generated 4 comments.






---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 52 out of 54 changed files in this pull request and generated 1 comment.




<details>
<summary>Suppressed comments (1)</summary>

**frontend/src/components/organisms/module/ModuleTable.vue:1284**
* `kindOptionsServerSearched` is meant to reflect “kind options are server-searched” (per the comment), but it currently checks `f.optionsSearch` on *any* field. If a future non-kind field uses `optionsSearch`, this would incorrectly skip taxonomy fetching (breaking kind/subkind label resolution and filters that still rely on taxonomy). Restrict the predicate to the kind field to match the intent and the ModuleForm logic.
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 54 out of 56 changed files in this pull request and generated 1 comment.




<details>
<summary>Suppressed comments (3)</summary>

**Previously missed (2)** — in code that hasn't changed since the last review.

**frontend/src/components/organisms/module/ModuleTable.vue:1410**
* This comment says the row’s backend-resolved label is checked *before* the taxonomy label map, but `kindCellLabel()` actually prefers the taxonomy map first. The mismatch is misleading for future maintenance (and the taxonomy-first precedence matches the tests/docstring in `classificationLabels.ts`).
**backend/app/repositories/data_entry_repo.py:837**
* The submodule `filter` value is interpolated directly into a `LIKE` pattern (`%{filter}%`) without escaping `%` / `_`, and the subsequent `ilike()` calls don’t use an escape character. This makes searches for literals like `100%` behave as wildcards (and can unintentionally broaden the query), which is inconsistent with the new typeahead implementation that explicitly escapes LIKE metacharacters.
```
        if filter:
            filter_pattern = f"%{filter}%"
            conditions = self._filter_conditions(
```

**frontend/src/components/organisms/module/ModuleTable.vue:1284**
* `kindOptionsServerSearched` currently treats *any* field with `optionsSearch` as a signal to skip fetching the submodule taxonomy. That’s broader than the intended “server-searched kind field” behavior and can accidentally skip taxonomy fetches when a different select adopts `optionsSearch`, breaking table label resolution for taxonomy-backed fields.
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 53 out of 55 changed files in this pull request and generated 1 comment.




<details>
<summary>Suppressed comments (1)</summary>

**frontend/src/components/molecules/VirtualSelectField.vue:119**
* In server-search mode, when the user input drops below 2 characters, the component returns without cancelling in-flight requests or resetting `serverLoading` / `loadError`. This can leave the field stuck in a loading/error state, and a slow previous request can still repopulate options after the input was cleared (because `requestSeq` is unchanged).
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 53 out of 55 changed files in this pull request and generated no new comments.




<details>
<summary>Suppressed comments (2)</summary>

**Previously missed (1)** — in code that hasn't changed since the last review.

**frontend/src/components/molecules/VirtualSelectField.vue:120**
* In server-search mode, dropping back below the 2-char threshold doesn't clear error/loading state and doesn't invalidate in-flight requests. If a request fails, `loadError` can remain stuck even after the user deletes input; and if a request resolves after the user backspaces to <2 chars, it can still update `serverOptions`, showing results for a query that is no longer active.

**frontend/src/components/molecules/VirtualSelectField.vue:35**
* The `#no-option` slot always shows “Type at least 2 characters to search” in server-search mode, even when the user has already typed 2+ chars and the server returns an empty list (or an error). This is misleading because it replaces Quasar’s default empty-state message.
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 55 out of 57 changed files in this pull request and generated no new comments.




<details>
<summary>Suppressed comments (2)</summary>

**Previously missed (2)** — in code that hasn't changed since the last review.

**frontend/src/components/molecules/VirtualSelectField.vue:120**
* In server-search mode, clearing the input back below 2 characters doesn’t invalidate any in-flight request. If a previous request resolves after the user has deleted the query, it can still update `serverOptions`/`loadError` because `requestSeq` is unchanged in the `< 2` early-return path, and `loadError` may also remain stuck true from a previous failure.
**backend/app/services/data_ingestion/base_factor_csv_provider.py:568**
* This docstring says a translation “never lands without the factors it labels”, but `_collect_translations()` is called before row validation in `_process_row`, so labels from rows that later fail validation can still be collected and upserted. Either move collection after validation, or adjust the docstring to avoid stating an invariant the code doesn’t guarantee.
```
        Runs in the same transaction as the factor batch above (both flush
        on the same commit at the end of ``ingest()``) — a translation
        never lands without the factors it labels, and vice versa.
```
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 56 out of 58 changed files in this pull request and generated 1 comment.




<details>
<summary>Suppressed comments (2)</summary>

**frontend/src/components/molecules/VirtualSelectField.vue:37**
* In server-search mode, the `#no-option` slot always shows “Type at least 2 characters…” even when the user has typed ≥2 chars and the server returns zero matches. That’s misleading (it’s a real “no results” state, not “keep typing”). Consider switching the message based on the current input length (slot scope exposes the input value) and falling back to an existing generic empty-state string for the ≥2 case (e.g. `common_no_items`).
**backend/alembic/versions/2026_09_01_0936-956c36805397_trigram_index_on_classification_.py:46**
* This migration’s `create_index` call passes `[sa.text("label gin_trgm_ops")]` as the column list. Alembic/Postgres index creation typically expects the column name in `columns` and the opclass in `postgresql_ops` (as used in the existing `ix_locations_keywords` trigram index). As written, this risks generating invalid SQL (treating `label gin_trgm_ops` as an expression) and failing at migrate time.
```
def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_classification_translations_label_trgm",
        "classification_translations",
        [sa.text("label gin_trgm_ops")],
        unique=False,
        postgresql_using="gin",
    )
```
</details>


---
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

Copilot reviewed 57 out of 59 changed files in this pull request and generated no new comments.




<details>
<summary>Suppressed comments (1)</summary>

**frontend/src/components/molecules/VirtualSelectField.vue:120**
* In server-search mode, the `<2 chars` early-return doesn’t invalidate any in-flight request and doesn’t reset `serverLoading`/`loadError`. If the user types a 2+ char query (request in flight) then deletes back to 1 char, the old request can still resolve and overwrite `serverOptions`, and a previous error can remain “sticky” even though no request is active.
</details>


---
### File: `backend/tests/unit/v1/test_taxonomy_options_endpoint.py` (Line 108) — github-advanced-security[bot]

## CodeQL / Unnecessary lambda

This 'lambda' is just a simple wrapper around a callable object. Use that object directly.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1342)
---
### File: `backend/tests/unit/v1/test_taxonomy_options_endpoint.py` (Line 109) — github-advanced-security[bot]

## CodeQL / Unnecessary lambda

This 'lambda' is just a simple wrapper around a callable object. Use that object directly.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1343)
---
### File: `frontend/src/components/molecules/ServerSearchSelectField.vue` (Line null) — Copilot

`loadError` (and potentially `loading`) is not reset when the query is <2 chars or `year` is null. After a failed request, clearing/shortening the input can leave the field stuck in an error state even though no request is being made.
---
### File: `frontend/src/stores/modules.ts` (Line null) — Copilot

The locale watcher triggers async store fetchers without awaiting/handling the returned Promises. This can trip `no-floating-promises`/unhandled-rejection tooling and makes intent unclear; use `void` (or `.catch(...)`) for fire-and-forget calls.
---
### File: `frontend/src/components/organisms/module/ModuleTable.vue` (Line 1282) — Copilot

`kindOptionsServerSearched` currently checks `f.optionsSearch` on *any* field, which could incorrectly skip taxonomy fetches if a non-kind field ever sets `optionsSearch`. This flag is meant to apply to the kind select only, so gate on `optionsId === 'kind'` as well (matching ModuleForm's logic).
---
### File: `backend/app/repositories/data_entry_repo.py` (Line 730) — Copilot

For the code+label-field shape, `matching_codes` is built from `Factor` without scoping by `data_entry_type_id` and year. That can (a) match codes that aren’t present in the current year’s factor catalog and (b) force a much larger scan of `factors` than needed.
---
### File: `frontend/src/components/molecules/ServerSearchSelectField.vue` (Line null) — Copilot

The `no-option` slot always renders “Type at least 2 characters…” even when the options request failed (`loadError=true`), which is misleading because the user already typed enough and the component is in an error state. Show an error message in the dropdown when `loadError` is set (or omit the slot entirely and rely on Quasar’s default no-results message).
---
### File: `backend/alembic/versions/2026_09_01_0936-956c36805397_trigram_index_on_classification_.py` (Line 46) — Copilot

Alembic’s `op.create_index` supports trigram opclasses via `postgresql_ops` (see the existing `locations.keywords` GIN index). Passing `sa.text("label gin_trgm_ops")` as a column expression is non-standard and may fail or generate different DDL across SQLAlchemy/Alembic versions.
---
### File: `frontend/src/components/molecules/VirtualSelectField.vue` (Line 35) — Copilot

The `#no-option` slot is always overridden in server-search mode with the “Type at least 2 characters…” message, so users who *did* type ≥2 chars but got no matches (or hit a load error) will still see the min-length instruction. This makes empty-result and error states misleading; consider showing this hint only when the current trimmed query length is <2, and otherwise fall back to Quasar’s default “no results” rendering (or a dedicated i18n key).

This issue also appears on line 115 of the same file.
---
### File: `frontend/src/components/molecules/VirtualSelectField.vue` (Line 120) — Copilot

When the input drops below 2 characters, `filterFn` returns without bumping `requestSeq` or resetting `serverLoading`/`loadError`. This allows an in-flight request from a previous ≥2 query to still apply its results (because `seq === requestSeq`), and it can also leave a stale error state visible after the user clears the input.
---

## Action Items

### Critical: logic, security, correctness

- [ ] **frontend/src/components/molecules/VirtualSelectField.vue** — the `< 2 chars` early-return in `filterFn` leaves `requestSeq` unbumped and `serverLoading`/`loadError` untouched, so a still-in-flight request repopulates options for a dead query and a failed request's error sticks after the user clears input (5 duplicate bot comments, plus 2 legacy ones on the since-deleted `ServerSearchSelectField` — one root cause). Fix: in that branch do `requestSeq++`, `serverLoading.value = false`, `loadError.value = false` before seeding options. Verified against the current code.
- [ ] **backend/app/services/data_ingestion/base_factor_csv_provider.py** — `_collect_translations` runs before row validation in `_process_row`, so a row that later fails validation still gets its `_fr` label upserted; the docstring's "a translation never lands without the factors it labels" is currently false for rejected rows. Fix: move the `_collect_translations(row, classification)` call to after the row's DTO validation succeeds (next to where the `Factor` is actually built/returned), keeping the invariant true rather than softening the docstring. Verified: collection sits right after classification build at ~line 384, validation follows.
- [ ] **backend/alembic/versions/2026_09_01_0936-956c36805397_trigram_index_on_classification_.py** — the index passes `[sa.text("label gin_trgm_ops")]` as the column list; the repo's own precedent (`ix_locations_keywords`, initial migration lines 224/1096) uses `["label"] + postgresql_ops={"label": "gin_trgm_ops"}`, which is stable across Alembic/SQLAlchemy versions. Fix: rewrite to the `postgresql_ops` form. Bot partially right: the raw SQL intent was validated on a scratch DB, but the text-expression rendering path wasn't — conform to precedent. (Migration is already applied locally: also `alembic downgrade -1` + re-upgrade locally after the edit, or drop/recreate the index manually.)
- [ ] **backend/app/repositories/data_entry_repo.py** — the table filter interpolates the raw term into `%{filter}%` with no escaping while the new typeahead escapes LIKE metacharacters — searching `100%` in a table still wildcard-matches (pre-existing flaw, but this PR created the inconsistency). Fix: reuse `_escape_like` from `factor_repo` in `_apply_name_filter`, and add `escape="\\"` to every `ilike()` in `_filter_conditions` (raw map conditions, translated-label subqueries, factor hop); add a regression test with a literal `%` term.

### Maintainability / refactoring

- [ ] **frontend/src/components/organisms/module/ModuleTable.vue** — `kindOptionsServerSearched` is `.some((f) => f.optionsSearch)` over all fields; a future non-kind `optionsSearch` field would wrongly skip the taxonomy fetch for the whole submodule (latent — flagged by the internal review too). Fix: gate on `f.optionsId === 'kind' && f.optionsSearch`, matching ModuleForm.
- [ ] **frontend/src/components/molecules/VirtualSelectField.vue** — the server-mode `#no-option` slot always says "Type at least 2 characters", which is wrong once the user typed ≥2 chars and got zero matches. Fix: track the last trimmed query length in `filterFn`; show the min-2 hint only below 2 chars and a genuine no-results message otherwise (reuse an existing i18n empty-state key if one exists, else add one to `common.ts` in both languages). Error state already surfaces under the field — the dropdown needs only the two-way split.
- [ ] **backend/tests/unit/v1/test_taxonomy_options_endpoint.py** (lines 108–109) — CodeQL "unnecessary lambda" ×2: `lambda: object()` / `lambda: MagicMock()` as dependency overrides. Fix: pass `object` and `MagicMock` directly (FastAPI calls the override; behavior identical). Closes code-scanning alerts 1342/1343.

### Dropped after verification

- Unscoped `matching_codes` factor hop — **already-fixed** (det + factor-year scoping shipped in the review-fixes commit; regression-tested).
- ModuleTable label-precedence comment mismatch — **already-fixed** (the inline rewrite documents taxonomy-first).
- Floating promises in the store locale watcher — **already-fixed/moot**: that watcher was deleted; the remaining unawaited store calls in ModuleTable match the established house pattern and lint passes.
- 8 Copilot quota-failure stubs — noise.
---
