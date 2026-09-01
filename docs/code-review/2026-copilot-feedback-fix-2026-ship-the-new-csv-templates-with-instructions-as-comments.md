# Bot Review TODOs: PR #2323

Source Branch: `fix/2026-csv-template-instructions`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Refreshes the downloadable CSV templates and updates the shared CSV reader to ignore inline `#` instruction lines.

**Changes:**

- Adds comment stripping before delimiter detection, including multiline-field handling.
- Updates templates with corrected encoding, dates, filenames, and sample data.
- Adds parser and shipped-template regression tests plus implementation documentation.

### Reviewed changes

Copilot reviewed 25 out of 25 changed files in this pull request and generated 8 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                           | Summary                                                                    |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| `frontend/public/templates/travel_trains_template.csv`                         | Updated travel template.                                                   |
| `frontend/public/templates/travel_planes_template.csv`                         | Updated travel template and numbering.                                     |
| `frontend/public/templates/researchfacilities_common_template.csv`             | Updated reference data template.                                           |
| `frontend/public/templates/researchfacilities_animals_template.csv`            | Updated template.                                                          |
| `frontend/public/templates/purchases_vehicles_template.csv`                    | Updated template.                                                          |
| `frontend/public/templates/purchases_services_template.csv`                    | Updated template.                                                          |
| `frontend/public/templates/purchases_scientificequipment_template.csv`         | Updated template.                                                          |
| `frontend/public/templates/purchases_other_template.csv`                       | Updated template.                                                          |
| `frontend/public/templates/purchases_itequipment_template.csv`                 | Updated template.                                                          |
| `frontend/public/templates/purchases_consumables_template.csv`                 | Updated template.                                                          |
| `frontend/public/templates/purchases_biological_chemical_gaseous_template.csv` | Updated template.                                                          |
| `frontend/public/templates/purchases_additional_template.csv`                  | Updated template.                                                          |
| `frontend/public/templates/processemissions_template.csv`                      | Critical (3 votes): currently has no matching process-emissions factors.   |
| `frontend/public/templates/headcount_template.csv`                             | Nit (2 votes): instruction uses the wrong header name.                     |
| `frontend/public/templates/external_clouds_template.csv`                       | Updated template.                                                          |
| `frontend/public/templates/external_ai_template.csv`                           | Critical (3 votes): instruction row is still parsed as invalid data.       |
| `frontend/public/templates/equipment_scientific_template.csv`                  | Critical (1 vote): example rows omit required equipment names.             |
| `frontend/public/templates/equipment_other_template.csv`                       | Critical (1 vote): example rows omit required equipment names.             |
| `frontend/public/templates/equipment_IT_template.csv`                          | Critical (1 vote): example rows omit required equipment names.             |
| `frontend/public/templates/building_rooms_template.csv`                        | Critical (3 votes): instruction row is still parsed as invalid data.       |
| `frontend/public/templates/building_energycombustions_template.csv`            | Updated template.                                                          |
| `docs/src/implementation-plans/2026-csv-template-instructions.md`              | Documents the implementation plan.                                         |
| `backend/tests/unit/utils/test_csv_dialect.py`                                 | Adds CSV comment parsing tests.                                            |
| `backend/tests/unit/test_shipped_csv_templates.py`                             | Moderate (3 votes): regression checks miss ordinary-text instruction rows. |
| `backend/app/utils/csv_dialect.py`                                             | Adds comment-aware CSV reading.                                            |

</details>

<details>
<summary>Suppressed comments (2)</summary>

**backend/app/utils/csv_dialect.py:56**

- Once this reader strips instruction rows, `BaseCSVProvider` still derives `total_rows` from the unfiltered CSV text while `processed` advances over this filtered reader. Every template consequently reports an inflated parsing total/ETA by the number of instructions and cannot reach that total; reuse the filtered text or calculate progress from the same filtered stream.

```
    uncommented = strip_comment_lines(csv_text)
```

**frontend/public/templates/travel_planes_template.csv:4**

- `NYC` is a metropolitan code, not an airport code, while plane emissions resolve locations by the exact `Location.iata_code` airport field. A user copying this example can therefore create an unresolved flight with no calculated emissions; use a real airport example such as `JFK` for New York.

```
#2) Enter the 3-letter IATA code for the destination airport (e.g., 'NYC' for New York, 'LHR' for London).
```

</details>

---

💡 <a href="/EPFL-ENAC/co2-calculator/new/dev?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 25 out of 25 changed files in this pull request and generated 10 comments.

<details>
<summary>Suppressed comments (2)</summary>

**frontend/public/templates/equipment_scientific_template.csv:146**

- These rows contain mojibake degree symbols ("Â°C"), which will display incorrectly in the template and should be corrected to "°C".

```
Lab Freezer / Frigde,Old -80Â°C freezers (>12yo),,,,,
Lab Freezer / Frigde,Recent -80Â°C freezers (<12yo),,,,,
Lab Freezer / Frigde,Small +4Â°C or -20Â°C freezers (< 150L),,,,,
Lab Freezer / Frigde,Big +4Â°C or -20Â°C freezers (> 150L),,,,,
```

**frontend/public/templates/equipment_scientific_template.csv:106**

- These rows contain mojibake characters ("Â°C" and "â€¦"), which indicates incorrect re-encoding and will render broken characters in the template. They should be corrected to "°C" and "…".

```
Agitator / Incubator,30 to 37Â°C incubators,,,,,
Agitator / Incubator,"Bench agitators (vortex, rockers, platforms, magnetic agitators, thermomixersâ€¦)",,,,,
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 27 out of 27 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (5)</summary>

**frontend/public/templates/building_rooms_template.csv:2**

- Line 2 is an instruction row but is missing the leading '#' (and also has a typo). As written, it will be treated as data by the importer and will likely create a failing upload row, defeating the purpose of comment-prefixed instructions.

```
Instructons: ,,,,
```

**frontend/public/templates/external_ai_template.csv:6**

- This instruction line is not prefixed with '#', so it will be parsed as a real data row (with empty required columns like fte_count) and will produce an avoidable validation error on upload. Prefix it with '#' so the shared reader strips it.

```
"1-5 times per day (1_5), 5-20 times per day (5_20), 20-100 times per day (20_100),>100 times per day (gt_100)",,,,
```

**frontend/public/templates/travel_trains_template.csv:11**

- The destination station name is mojibake (likely an encoding/conversion artifact): `GenÃ¨ve` should be `Genève`. Since templates are user-facing examples, keep the sample data correctly encoded to avoid copy/paste errors and confusion.

```
Lausanne,CH,GenÃ¨ve,CH,234567,2025-12-03,1,second,
```

**frontend/public/templates/purchases_vehicles_template.csv:15**

- Several sample values appear mojibake-encoded (e.g. `VÃ©hicule`, `Remorque Ã  bateau`, `MÃ©canique`). These should be proper UTF-8 text with correct accents so users don't copy broken strings into uploads.

```
VÃ©hicule piquet MCR,Emil Frey AG,1.0,31155.95,chf,25100000,BF14,,
"Remorque Ã  bateau, longueur maximum du b",MÃ©canique Navale de A Ã  Z SÃ rl,1.0,6105.45,chf,25101900,AD15,,
"Pose des roues Ã©tÃ©, selon devis du 28/04",LARAG SA Echandens,1.0,371.95,chf,25100000,AD01,,
```

**frontend/public/templates/headcount_template.csv:5**

- Instruction text references a non-existent column name (`user_institution_id`). The header is `user_institutional_id`, so users following the instructions will be misled.

```
# 3) Insert the institutional id (SCIPER) of the person in the column user_institution_id.,,,,
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 27 out of 27 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (7)</summary>

**Previously missed (1)** — in code that hasn't changed since the last review.

**frontend/public/templates/processemissions_template.csv:5**

- The template claims users can fill the kg_co2eq column to override calculation, but the backend process emissions handler computes emissions from quantity_kg × factor and does not use an uploaded kg_co2eq value for computation (so the column is misleading).

```
# 3) If known you can specify directly the amount of carbon emissions in kg for a certain category/subcategory by filling the column kg_co2eq. Otherwise if this column is left empty the calculator will do the calculation for you.,,,,
```

**frontend/public/templates/building_rooms_template.csv:2**

- Line 2 is an instruction row but it does not start with “#”, so it will be treated as data and may cause confusing upload failures; it also has a typo (“Instructons”).

```
Instructons: ,,,,
```

**frontend/public/templates/external_ai_template.csv:6**

- This instruction line is missing the leading “#”, so it will be imported as a data row (and likely fail validation) instead of being skipped by strip_comment_lines.

```
"1-5 times per day (1_5), 5-20 times per day (5_20), 20-100 times per day (20_100),>100 times per day (gt_100)",,,,
```

**frontend/public/templates/headcount_template.csv:5**

- The instructions reference the wrong column name (user_institution_id). The header column is user_institutional_id, so this is misleading for users filling the template.

```
# 3) Insert the institutional id (SCIPER) of the person in the column user_institution_id.,,,,
```

**frontend/public/templates/travel_trains_template.csv:11**

- The example destination name is mojibake (GenÃ¨ve). Templates should ship with correctly encoded/decoded human-readable values, especially for common locations.

```
Lausanne,CH,GenÃ¨ve,CH,234567,2025-12-03,1,second,
```

**frontend/public/templates/equipment_scientific_template.csv:106**

- These reference-list values contain mojibake characters (e.g. “Â°C”, “â€¦”). For equipment templates, these strings need to be exact because they are used for factor matching; wrong characters can make uploads fail.

```
Agitator / Incubator,30 to 37Â°C incubators,,,,,
Agitator / Incubator,"Bench agitators (vortex, rockers, platforms, magnetic agitators, thermomixersâ€¦)",,,,,
```

**frontend/public/templates/equipment_scientific_template.csv:89**

- This line contains mojibake (“â€¦”) in a reference-list entry; it should be the actual ellipsis character (“…”) to avoid mismatches with the factor catalog and to keep the template readable.

```
Optical microscopes,"Simple microscopes, reversed microscopes, and binocular lenses,â€¦",,,,,
```

</details>

---

### File: `backend/tests/unit/test_shipped_csv_templates.py` (Line 53) — Copilot

This assertion only rejects rows whose value begins with `#`, so ordinary-text instruction rows still pass it. The current `building_rooms` and `external_ai` templates therefore evade this regression suite even though the importer treats those rows as data and rejects them; validate each template's non-comment rows against its required schema or add a stronger instruction-row check.
---

### File: `frontend/public/templates/building_rooms_template.csv` (Line null) — Copilot

This row is still parsed as data because it does not start with `#`. Since `building_name` and `room_name` are required, uploading the downloaded template produces a validation error for the instruction itself. Make this line `#Instructions:` so the template remains uploadable.
---

### File: `frontend/public/templates/equipment_IT_template.csv` (Line null) — Copilot

`EquipmentHandlerCreate.name` is required and rejects an empty string, but every example row in this template leaves the second column blank. Uploading the downloaded template will therefore reject all of these rows; populate the name column (or change the importer contract if this is meant to be reference-only data) before shipping.
---

### File: `frontend/public/templates/equipment_other_template.csv` (Line null) — Copilot

`EquipmentHandlerCreate.name` is required and rejects an empty string, but every example row in this template leaves the second column blank. Uploading the downloaded template will therefore reject all of these rows; populate the name column (or change the importer contract if this is meant to be reference-only data) before shipping.
---

### File: `frontend/public/templates/equipment_scientific_template.csv` (Line null) — Copilot

`EquipmentHandlerCreate.name` is required and rejects an empty string, but every example row in this template leaves the second column blank. Uploading the downloaded template will therefore reject all of these rows; populate the name column (or change the importer contract if this is meant to be reference-only data) before shipping.
---

### File: `frontend/public/templates/external_ai_template.csv` (Line null) — Copilot

This instruction is still an ordinary CSV row, so the importer treats it as an AI entry with an invalid provider and missing required fields. The shipped-template checks also miss it because the value does not start with `#`; prefix the row with `#` so it is actually ignored.
---

### File: `frontend/public/templates/headcount_template.csv` (Line null) — Copilot

The header uses `user_institutional_id`, but this instruction tells users to populate `user_institution_id`. Following the instruction can lead to a renamed column and the required-header validation will reject the upload; use the exact header name here.
---

### File: `frontend/public/templates/processemissions_template.csv` (Line null) — Copilot

The template still cannot produce emissions with the factor set currently shipped by the application: the PR reports 0/62 rows matching. Because missing primary factors yield no computation, uploading this file persists rows without process-emissions totals; hold or regenerate it after the data-owner confirmation in #2026.
---

### File: `frontend/public/templates/building_rooms_template.csv` (Line 2) — Copilot

Line 2 is an instruction but it does not start with `#`, so it will be imported as a data row (and it also contains a spelling typo). This defeats the new "comment lines" convention and can make the shipped template fail on upload.
---

### File: `frontend/public/templates/external_ai_template.csv` (Line 6) — Copilot

This line is part of the instructions block but it does not start with `#`, so it will reach the importer as a data row and likely fail validation on upload. It should be a `#` comment line like the rest of the instructions.
---

### File: `frontend/public/templates/headcount_template.csv` (Line 5) — Copilot

The instructions reference a non-existent column name (`user_institution_id`). The header uses `user_institutional_id`, so users following the instructions will fill the wrong column.
---

### File: `frontend/public/templates/travel_trains_template.csv` (Line 11) — Copilot

This example row contains mojibake ("GenÃ¨ve") instead of the intended accented name ("Genève"), indicating the template text was re-encoded incorrectly. Since these templates are user-facing, the example data should use correct UTF-8 characters.
---

### File: `frontend/public/templates/purchases_vehicles_template.csv` (Line 15) — Copilot

These sample rows contain mojibake (e.g. "VÃ©hicule", "Remorque Ã ", "MÃ©canique"), which suggests the file content was double-encoded and will display incorrectly for users.
---

### File: `frontend/public/templates/purchases_services_template.csv` (Line 16) — Copilot

These sample rows contain mojibake (e.g. "Ã©", "DÃ©pannage", "Ã  l'enquÃªte"), which indicates the template content was re-encoded incorrectly and will render broken accents.
---

### File: `frontend/public/templates/purchases_consumables_template.csv` (Line 15) — Copilot

These sample rows contain mojibake ("piÃ¨ces", "BrÃ¼tsch-RÃ¼egger"), so the downloaded template will show broken accents in Excel/UI.
---

### File: `frontend/public/templates/purchases_other_template.csv` (Line 14) — Copilot

This sample row contains mojibake ("RÃ©gent"), so the template's sample data will render broken accents.
---

### File: `frontend/public/templates/purchases_itequipment_template.csv` (Line 15) — Copilot

These sample rows contain mojibake / broken punctuation (e.g. "Ã‰cran", "Â ", "â€”"), indicating incorrect re-encoding. This will display incorrectly for users and can be fixed by restoring proper UTF-8 characters (É, non-breaking spaces or regular spaces, and an em dash).
---

### File: `frontend/public/templates/equipment_scientific_template.csv` (Line 89) — Copilot

This row contains mojibake ("â€¦"), which will display as broken characters in the downloadable template. Replace it with the intended ellipsis character ("…").

This issue also appears in the following locations of the same file:

- line 105
- line 143

---

## Action Items

Triage of 2026-09-01, verified against the branch after the `templates_2026-09-01` pack landed. All valid items below were fixed in the same session; checklist kept as the record.

### Critical: logic, security, correctness

- [x] **frontend/public/templates/** (7 files) — Mojibake from double-encoded UTF-8 (`GenÃ¨ve`, `Â°C`, `â€¦`…) in travel_trains, 5 purchases files and equipment_scientific. In equipment_scientific the broken strings are `sub_class` factor-matching keys and the factor table has the clean `°C`/`…` forms, so those rows would miss their factor. Fix: repaired by cp1252 round-trip, every changed cell reviewed. Copilot was right; also asked upstream to re-export cleanly.
- [x] **frontend/public/templates/building_rooms_template.csv** — Line 2 `Instructons: ,,,,` has no `#` (plus a typo), so it imports as a data row and fails. Fix: rewritten to `# Instructions:,,,,`.
- [x] **frontend/public/templates/external_ai_template.csv** — The frequency-categories continuation line is quote-wrapped, not `#`-prefixed, so it imports as a data row and fails. Fix: rewritten as a `#` line.
- [x] **backend/tests/unit/test_shipped_csv_templates.py** — The leak check only flags cells that still start with `#`, so instruction rows that lost the marker pass. Fix: added an instruction-prose check (catches both rows above) and a mojibake check; both verified to fail on the raw pack.

### Performance

- [x] **backend/app/services/data_ingestion/base_csv_provider.py** — Progress total counted raw newlines while the row loop iterates the comment-stripped reader, so ingests report a total they never reach. Fix: count on `strip_comment_lines(csv_text)`. Cosmetic (ETA display only), fixed since it is one line.

### Maintainability / refactoring

- [x] **frontend/public/templates/headcount_template.csv** — Instruction 3 names a column that does not exist (`user_institution_id` vs header `user_institutional_id`). Fix: corrected the instruction.
- [x] **frontend/public/templates/travel_planes_template.csv** — Instruction example uses `NYC`, a metropolitan code the plane location lookup (exact `iata_code`) cannot resolve. Fix: example changed to `JFK`.

### Dropped after verification

- **processemissions matches no factors / "hold the template"** — stale: the #2197 factor rename shipped and the data owner confirmed the uploaded factors match; all 9 template categories match `_PROCESS_GAS_MAP`.
- **kg_co2eq column is misleading, backend ignores it** — wrong: uploads carry `kg_co2eq` out-of-band as `__kg_co2eq_override__` and `prepare_create` honors it for every module (`data_entry_emission_service.py`).
- **equipment templates leave `name` empty so every row fails** — by design: those templates are reference lists (same shape as the previous set); users keep only the rows they own and fill `equipment_id`/`name`.

---
