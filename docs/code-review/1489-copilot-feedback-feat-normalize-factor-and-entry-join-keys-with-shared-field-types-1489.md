# Bot Review TODOs: PR #2585

Source Branch: `feat/1489-factor-entry-normalization`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Implements the normalization portion of #1489 by introducing shared Pydantic field aliases to canonicalize factor/entry join keys (casing/whitespace/numeric-id quirks) and by migrating existing `factors.classification` rows to that same canonical form (including merging duplicates and repointing emissions).

**Changes:**

- Added shared normalized field types (`CurrencyCode`, `CountryCode`, `ClassificationKey`, `OptionalClassificationKey`, `IdentifierKey`) and applied them symmetrically across factor + entry DTOs for join-key fields.
- Ensured normalized DTO values actually persist by syncing validated DTO fields back into `data_entries.data`, and by having the factor CSV provider copy validated DTO values into `classification`.
- Added a data migration to normalize `factors.classification` and merge post-normalization duplicates safely (repoint emissions before deletes), plus regression tests to pin behavior.

### Reviewed changes

Copilot reviewed 26 out of 26 changed files in this pull request and generated no comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                           | Description                                                                                                               |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| docs/src/implementation-plans/1489-factor-entry-normalization.md                               | Documents the shipped approach, deviations, migration behavior, and test coverage.                                        |
| backend/app/schemas/fields.py                                                                  | New shared annotated field types implementing canonical forms for join keys.                                              |
| backend/app/schemas/data_entry.py                                                              | Synces validated DTO field values back into persisted `data` (fixes “normalized fields not persisted” gap).               |
| backend/app/services/data_ingestion/base_factor_csv_provider.py                                | Copies DTO-normalized values into `classification` during CSV factor ingestion to keep upsert identity stable.            |
| backend/alembic/versions/2026_08_31_1935-09fe9e551783_normalize_factor_classification_join_.py | Normalizes stored factor classifications and merges duplicates while preserving emissions.                                |
| backend/app/modules/purchase/data_entries.py                                                   | Applies shared field types to purchase entry DTO join keys and relies on shared normalization.                            |
| backend/app/modules/purchase/factors.py                                                        | Applies shared field types to purchase factor DTO join keys; aligns optional-code blank handling and currency validation. |
| backend/app/modules/purchase/handlers.py                                                       | Keeps defensive currency lowercasing for pre-normalization persisted entries (documented).                                |
| backend/app/modules/professional_travel/data_entries.py                                        | Applies shared field types for travel join keys; normalizes cabin class with strip+lower.                                 |
| backend/app/modules/professional_travel/factors.py                                             | Applies shared field types for travel join keys; normalizes cabin class/country code consistently.                        |
| backend/app/modules/external_cloud_and_ai/data_entries.py                                      | Applies shared field types for join keys; keeps default-currency behavior without mutating caller payload.                |
| backend/app/modules/external_cloud_and_ai/factors.py                                           | Applies shared field types for join keys; aligns currency handling with normalized alias.                                 |
| backend/app/modules/process_emissions/data_entries.py                                          | Applies shared field types for join keys; blank optional keys normalize to `None`.                                        |
| backend/app/modules/process_emissions/factors.py                                               | Applies shared field types for join keys; blank optional keys normalize to `None`.                                        |
| backend/app/modules/equipment/data_entries.py                                                  | Applies shared field types for join keys (including optional subclass handling).                                          |
| backend/app/modules/equipment/factors.py                                                       | Applies shared field types for join keys (including optional subclass handling).                                          |
| backend/app/modules/buildings/data_entries.py                                                  | Applies shared field types for join keys (building/room identifiers).                                                     |
| backend/app/modules/buildings/factors.py                                                       | Applies shared field types for join keys (building/category identifiers).                                                 |
| backend/app/modules/research_facilities/data_entries.py                                        | Applies shared field types for research-facility join keys (including spreadsheet numeric id/name).                       |
| backend/app/modules/research_facilities/factors.py                                             | Applies shared field types for research-facility join keys (including spreadsheet numeric id/name).                       |
| backend/tests/unit/schemas/test_normalized_fields.py                                           | New regression suite covering alias canonical forms, `data` sync, resolver match, and migration/DTO symmetry pin.         |
| backend/tests/unit/services/data_ingestion/test_factor_csv_normalized_identity.py              | New regression test ensuring CSV re-import identity is stable under casing/whitespace noise.                              |
| backend/tests/unit/modules/test_purchase_schemas.py                                            | Updates expectations for optional-code normalization to `None`.                                                           |
| backend/tests/unit/modules/test_whitespace_required_strings.py                                 | Broadens validation-message matching to account for standardized constraint errors.                                       |
| backend/tests/unit/modules/test_research_facilities_schemas.py                                 | Updates expectations for standardized constraint errors after shared type adoption.                                       |

</details>

---

💡 <a href="/EPFL-ENAC/co2-calculator/new/dev?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review?tool=webui#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 26 out of 26 changed files in this pull request and generated 2 comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 28 out of 28 changed files in this pull request and generated 1 comment.

<details>
<summary>Suppressed comments (2)</summary>

**Previously missed (2)** — in code that hasn't changed since the last review.

**backend/app/modules/purchase/data_entries.py:60**

- ensure_default_currency only looks at the top-level "currency" key; if a caller passes the already-unflattened shape ("data": {...}) with currency inside data (or with top-level currency missing), this validator will incorrectly apply the default and the nested data won't be updated. Making the validator consider/sync the nested data makes the behavior robust and avoids relying on model-validator ordering.

```
            if currency is None or (
                isinstance(currency, str) and currency.strip() == ""
            ):
                # Copy: mutating the caller's dict leaks the default upstream.
                return {**data, "currency": "chf"}
```

**backend/alembic/versions/2026_08_31_1935-09fe9e551783_normalize_factor_classification_join\_.py:99**

- This migration loads all rows from the factors table into memory (fetchall), then issues per-group UPDATE/DELETE statements and per-row UPDATEs for normalization. On large deployments this can be slow and hold locks longer than necessary; consider rewriting as set-based SQL (normalize via jsonb updates + de-dupe with a window function) or at least batching/chunking the work to reduce migration time/lock contention.

```
    rows = bind.execute(
        sa.text(
            "SELECT id, data_entry_type_id, year, emission_type_id, classification"
            " FROM factors"
        )
    ).fetchall()
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 28 out of 28 changed files in this pull request and generated 1 comment.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 28 out of 28 changed files in this pull request and generated 1 comment.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 28 out of 28 changed files in this pull request and generated 1 comment.

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

### File: `docs/src/implementation-plans/1489-factor-entry-normalization.md` (Line null) — Copilot

The plan frontmatter marks this as `status: in-progress`, but this PR implements the normalization + migration + tests described below. Updating the status to `delivered` will keep the implementation-plans index/greps accurate once the PR merges.
---

### File: `backend/alembic/versions/2026_09_08_1000-09fe9e551783_normalize_factor_classification_join_.py` (Line 77) — Copilot

In the migration normalization, every whitespace-only string is converted to None (lines 75-76). That matches OptionalClassificationKey, but it does not match required join-key types like ClassificationKey/CurrencyCode, and it can also merge factors that differ only by a blank vs an absent key. Consider limiting blank→None to the known optional classification keys and leaving other blank required keys unchanged (or failing the migration) so identities don’t silently change.
---

### File: `backend/app/modules/external_cloud_and_ai/data_entries.py` (Line 63) — Copilot

ensure_default_currency only checks the top-level "currency" key; if a caller passes the already-unflattened payload shape ("data": {...}) with currency inside data (or missing at top-level), this will incorrectly inject the default and the nested payload stays unsynced. Consider the nested "data" currency too and keep both representations in sync to avoid relying on validator ordering.
---

### File: `backend/alembic/versions/2026_09_08_1000-09fe9e551783_normalize_factor_classification_join_.py` (Line 104) — Copilot

Using `.fetchall()` loads the entire `factors` table into memory during the migration. Since factors can be large (e.g., big CSV uploads), consider streaming the result set to reduce peak memory and lower the risk of long-running migration failures.
---

### File: `backend/alembic/versions/2026_09_08_1000-09fe9e551783_normalize_factor_classification_join_.py` (Line 77) — Copilot

Migration normalization for identifier join keys doesn’t mirror the new `IdentifierKey` behavior: `_normalize_value` returns non-strings unchanged, so pre-existing `classification` values stored as numeric JSON (e.g. `12` or `12.0`) would remain numeric instead of becoming the canonical string form ("12"), potentially preventing deduping and keeping resolution mismatches. Align this with `app.schemas.fields._coerce_numeric_identifier`, while still leaving booleans untouched.
---

### File: `backend/app/schemas/fields.py` (Line 83) — Copilot

The shared string aliases are not strict, so Pydantic will coerce non-string inputs (e.g., 42/True) into strings instead of raising. This undermines the intent of the before-validators (“pass through so Pydantic’s str type error surfaces”) and can let invalid join keys leak into persisted data/classification.
---

### File: `backend/tests/unit/schemas/test_entry_data_migration.py` (Line 75) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1347)
---

### File: `backend/app/schemas/factor.py` (Line 138) — github-advanced-security[bot]

## CodeQL / Statement has no effect

This statement has no effect.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1346)
---

---

## Action Items

### Performance

> Superseded the same day: both data migrations were removed on the lead's decision (see plan 1489). The chunked read lives on in `scripts/normalize_join_keys.py`.

- [x] **backend/alembic/versions/2026_09_08_1029-cf237968fba7_normalize_entry_data_join_keys.py** — the entry-data migration read the whole `data_entries` table with one `fetchall()`; a year of purchases is 150k rows per unit upload, so the migration Job's memory would scale with the table. Fix: keyset pagination (`id > :after_id ORDER BY id LIMIT 5000`), rewrite per chunk. Done in this branch. The same remark on the factor migration (`09fe9e551783`) is dropped: it needs every row in memory to group duplicates, and `factors` is bounded by the shipped CSVs (about 20k rows per year).

### Dropped after verification

- **Plan frontmatter `in-progress`** — already fixed (`delivered`, 2026-09-08).
- **`ensure_default_currency` ignores a nested `data` payload** (purchase + external cloud) — wrong: no caller hands the DTO a `{"data": {...}}` shape. The create/update workflows (`workflows/carbon_report_module.py`) and every CSV provider pass the flat row; `unflatten_payload` builds `data` itself. A nested shape would also fail the required-field validation on the create DTOs, so it cannot reach the validator unnoticed.
- **Factor migration turns blank required keys into `None` and could merge factors that differ by blank vs absent** — wrong: the CSV provider has always stored `None` for a blank classification cell (`value.strip() if value and value.strip() else None`) and the API create DTOs reject blank required keys, so `""` cannot exist in `factors.classification`. Absent keys are never added, so `{"k": null}` and `{}` keep distinct identities.
- **Factor migration leaves numeric JSON identifiers untouched** — wrong: factor classifications only ever come from CSV cells (provider and seeder both read through `csv_dict_reader`), so they are strings. The entry migration, where JSON numbers do occur, mirrors `_coerce_numeric_identifier` exactly and is pinned by `test_entry_data_migration.py`.
- **Shared aliases not strict, `42` coerced to `"42"`** — wrong: pydantic v2 rejects non-string input for `str` fields in lax mode; `test_non_string_inputs_pass_through_and_fail_type_check` pins it.
- **CodeQL "non-iterable used in for loop"** on `for det in DataEntryTypeEnum` — false positive on Enum iteration.
- **CodeQL "statement has no effect"** on the `Protocol` stub `validate_year_factors(...) -> None: ...` — false positive; identical to the sibling stubs on the lines above it.
