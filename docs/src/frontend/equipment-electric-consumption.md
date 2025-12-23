# Equipment Electric Consumption UX

Scope: frontend behaviors for the Equipment Electric Consumption module (tables, inline edits, power factors, validation, and visual cues).

## Table & Editing Rules

- Columns: Name | Class | Subclass | Active Use (hrs/wk) | Standby Use (hrs/wk) | Active Power (W) | Standby Power (W) | kg CO2-eq.
- Inline editable: Active Use, Standby Use only. Name and power columns are read-only. Class is editable only via the edit dialog with a disclaimer.
- Tooltips: power columns explain representativeness limits; kg CO2-eq notes uncertainty (per i18n strings).
- Search bar filters rows; “New” rows (is_new flag) show a badge and left highlight.

## Validation

- Active/Standby use must be numeric and 0–168 hrs/wk; errors shown inline.
- Rows missing required fields are marked incomplete and excluded from footprint aggregation.

## Power Factors

- On class edit, the UI calls `/api/v1/power-factors/{submodule}/classes/{class}/power?sub_class=` to auto-fill Active/Standby power using the power_factors table (subclass preferred, class fallback). Values remain read-only afterward.

## Footprint & Threshold Coloring

- Formula (Status == "In service"):
  \[
  \text{kgCO2-eq} = (\text{Active Use} \times \text{Active Power} + \text{Standby Use} \times \text{Standby Power}) \times EF \times 52
  \]
  with EF = swiss_mix = 0.125 for now.
- Threshold: fixed kg CO2-eq value from module config; coloring is implicit (red when exceeded, otherwise default). Hidden value until backoffice provides one.

## CSV Import/Export (Mock)

- Upload/download buttons currently show notify toasts only; no parsing/storage yet. Replace with real import/export when API is ready.

## Notes

- “New since last year” uses backend `is_new` when available; otherwise no badge.
- If subclass is absent, power-factor lookup falls back to class-only match.
- Keep power values sourced from power_factors (not editable, not stored on equipment row aside from fetched values).
