---
status: in-progress
issue: 2026
last_updated: 2026-09-01
title: "CSV templates: inline instructions as # comment lines"
summary: "The data manager delivered a new template pack (SharePoint _DATA_INPUT/templates, 2026-08-24) that carries filling instructions as ordinary CSV rows, plus three defects that fail on upload: two files in latin-1, US-format example dates, and four filenames the app does not serve. Teach the shared reader to skip #-prefixed lines, then ship the pack with the instructions rewritten as comments and the defects fixed."
---

# CSV templates: inline instructions as `#` comment lines

## Problem

Issue #2026 asked for filling instructions inside the CSV templates. The
delivered pack puts them in the data area, one instruction per row, ending
with "delete all these instructions lines before uploading". That makes the
instructions data:

- A user who forgets to delete them gets 4 to 11 failed rows in the upload
  report, drowning the real errors. `equipment_scientific` (160 rows) and
  `researchfacilities_common` (85 rows) double as reference lists, so the
  instructions sit inside the list people scroll.
- The template stops round-tripping. Download, fill, upload is the whole
  point of the file.

Three further defects in the same pack fail on upload regardless:

1. `travel_trains_template.csv` and `headcount_template.csv` are latin-1
   (`è` of Genève, non-breaking spaces in "Other teaching staff"). Ingestion
   decodes `utf-8-sig` strictly, so both die with "Wrong CSV format or
   encoding" before a row is read. No file in the pack carries the UTF-8 BOM
   that #2069 added so Excel stops mangling accents on re-save.
2. Every example date is US `M/D/YYYY` while the instruction line in the
   same file says ISO. `DepartureDateMixin.parse_departure_date` swaps `/`
   for `-` then calls `fromisoformat`, so `12-1-2025` raises: every example
   row in both travel templates is rejected.
3. Four filenames differ from what `templateMapping.ts` requests, so the
   download button 404s.

## Approach

Comment lines, not a second instructions file. Every ingestion path already
funnels through `csv_dict_reader`, so one change covers uploads, factors,
reference data and year config.

A line is a comment when `#` opens it _at a record boundary_. A `#` opening
a physical line inside a quoted multi-line field is data, and quote parity
tells the two apart — the existing
`test_csv_dict_reader_preserves_embedded_newlines_in_quoted_fields` shows
those fields are real here. The marker must be the first character of the
line: `equipment_data.csv` already holds a cell reading `#03 INN 215`, and
a rule loose enough to catch that would silently eat a data row.

Comments are stripped before delimiter sniffing, so comma-heavy instruction
prose in a semicolon file cannot sway the detected delimiter.

## Steps

- [x] `strip_comment_lines` in `app/utils/csv_dialect.py`, applied inside
      `csv_dict_reader` before sniffing. Unit tests for the quoted-field and
      `#`-inside-a-cell cases.
- [x] Convert the pack into `frontend/public/templates/`: instructions to
      `#` lines, dates to ISO, re-encode UTF-8 + BOM, the four renames.
- [x] Regression test walking every shipped template through the real
      reader (`tests/unit/test_shipped_csv_templates.py`). It fails on all
      three defects above, which is how they were found.
- [x] Replace with the re-delivered pack (SharePoint
      `_DATA_INPUT/templates_2026-08-27`). It fixes the encoding (UTF-8 +
      BOM everywhere), the dates, the `#` prefixes and one of the four
      filenames at the source.
- [ ] Test round with the data owners, then close #2026.

## Divergences from the delivered pack (2026-08-27 re-delivery)

The first pack's date/encoding/`#` rewrites are now fixed at the source.
Our copy still differs from SharePoint on these points, kept deliberately
and reported on the issue so the next regeneration folds them in:

- Two renames the app requires: `equipment_it` → `equipment_IT`,
  `purchases_scientific_equipment` → `purchases_scientificequipment`.
  For the third one the data owner is right: the submodule is centralized
  purchases, so we kept her `purchases_centralized_template.csv` and
  renamed the file the app serves instead (`templateMapping.ts` pointed
  at `purchases_additional_template.csv`).
- `processemissions` line 5 arrived quote-wrapped (`"# 3) ..."""`), so the
  comment stripper saw `"` first and the line leaked as a data row.
  Unquoted it.
- Both `researchfacilities` files dropped `kg_co2eq` from the header but
  every data row kept its trailing empty field. The importer filters extra
  columns, but the width test is strict on purpose; trimmed.
- The closing "delete all these instructions lines" instruction now reads
  that `#` lines are ignored and can stay.
- Instruction numbering renumbered (the pack skips 7 in `travel_planes`).

## Open question (equipment factors)

The re-delivered equipment templates re-categorize the catalog: scientific
goes 138 → 161 classes, it 25 → 22, other 7 → 23 (Autoclaves, Photocopy
machines, Kitchen… moved to other; Lab Freezer moved to scientific). The
factor lookup is scoped per submodule and equipment requires a factor per
row, so those rows fail with "no matching factor" unless a re-categorized
equipment factors file is uploaded too — asked on #2026. Shipping the
templates as delivered is safe either way: the failure is loud, not silent.

## Out of scope

- `purchases_common_template.csv` is absent from the pack and kept from the
  previous set; the Purchase module falls back to it.
- `MODULE_DEFAULTS` in `templateMapping.ts` points Equipment at
  `equipments_template.csv`, which has never existed. Pre-existing 404,
  separate issue.
- `backend/INPUT_DATA/*_template.csv` are unreferenced copies (nothing in
  `app/` or `tests/` reads them). Left alone; they want deleting, not
  updating.
