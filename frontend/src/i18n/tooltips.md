# Tooltip Translation Guide

This guide explains how to add or update the small **(ℹ) tooltip icons** shown throughout the CO2 calculator.

All tooltip text lives in a single file: **`frontend/src/i18n/tooltips.ts`**

---

## Step 1 — Find the right key

Each tooltip has a unique name called a **key**. The key tells the app where the tooltip appears. Use the table below to find the key pattern for the tooltip you want to edit.

| Where you see the (ℹ) icon in the app                                         | Key pattern                                                       | Example                                                                    |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Top-right corner of a module page                                             | `module-{module}-title`                                           | `module-headcount-title`                                                   |
| Next to a sub-section title (e.g. "Scientific Equipment")                     | `module-{module}-submodule-{submodule}`                           | `module-buildings-submodule-building`                                      |
| Top of a data-entry form (the dialog that opens when adding or editing a row) | `module-{module}-submodule-{submodule}-form`                      | `module-equipment-electric-consumption-submodule-scientific-form`          |
| Next to a column header in a data table                                       | `module-{module}-submodule-{submodule}-table-{column}`            | `module-buildings-submodule-building-table-room_allocation_ratio`          |
| Next to a module chart title                                                  | `module-{module}-charts`                                          | `module-buildings-charts`                                                  |
| On a summary stat card in the Results page                                    | `results-stats-{stat}-title`                                      | `results-stats-total-unit-carbon-footprint-title`                          |
| On a chart title or filter badge in the Results page                          | `results-charts-{chart}-title` or `results-charts-{chart}-filter` | `results-charts-it-focus-breakdown-title`                                  |
| Next to a reduction slider label                                              | `results-reduction-{category}`                                    | `results-reduction-professional_travel`                                    |
| On a module-specific stat card in the Results page                            | `results-{module}-stats-{stat}-title`                             | `results-equipment-electric-consumption-stats-total-electricity-use-title` |
| In the admin back-office pages                                                | `backoffice-{page}-{description}`                                 | `backoffice-data-management-open-year-disabled`                            |

Replace `{module}`, `{submodule}`, `{column}`, etc. with the slug from the tables at the bottom of this guide.

---

## Step 2 — Edit the text

Open `tooltips.ts`, find the key you identified, and update the text between the quotes:

```ts
'module-headcount-title': {
  en: 'Write your English text here.',
  fr: 'Écrivez votre texte en français ici.',
},
```

### To hide a tooltip icon completely

Set both `en` and `fr` to empty strings. The icon will disappear from the app:

```ts
'module-buildings-title': {
  en: '',
  fr: '',
},
```

> **⚠️ Never delete a key line.** If a key is missing from the file entirely, the app will show the raw key name (e.g. `module-buildings-title`) as visible text on screen instead of hiding the icon. Always keep the line, even when the values are empty.

---

## Step 3 — Adding a tooltip to a table column (extra step)

If you want a (ℹ) icon on a table column that does not yet have one, two things are needed:

1. Add the key and text to `tooltips.ts` (following Step 2 above).
2. Also add `tooltip: 'your-key'` to that column's definition in the file
   `frontend/src/constant/module-config/<module>.ts`.

Ask a developer to help with step 2 if needed.

---

## Module name slugs

Use the **Slug** column exactly as written when building a key. Modules are listed in the order they appear in the app.

| Module              | Slug                             |
| ------------------- | -------------------------------- |
| Headcount           | `headcount`                      |
| Process Emissions   | `process-emissions`              |
| Buildings           | `buildings`                      |
| Equipment           | `equipment-electric-consumption` |
| External Cloud & AI | `external-cloud-and-ai`          |
| Professional Travel | `professional-travel`            |
| Purchase            | `purchase`                       |
| Research Facilities | `research-facilities`            |

---

## Submodule name slugs

Each module is divided into sub-sections. Use the **Slug** column exactly as written. Sub-sections are grouped by their module, in app order.

| Module              | Sub-section               | Slug                                  |
| ------------------- | ------------------------- | ------------------------------------- |
| Headcount           | FTE members               | `member`                              |
| Headcount           | Students                  | `student`                             |
| Process Emissions   | Process emissions         | `process_emissions`                   |
| Buildings           | Rooms                     | `building`                            |
| Buildings           | Heating Combustion        | `energy_combustion`                   |
| Equipment           | Scientific                | `scientific`                          |
| Equipment           | IT                        | `it`                                  |
| Equipment           | Other                     | `other`                               |
| External Cloud & AI | Cloud services            | `external_clouds`                     |
| External Cloud & AI | AI services               | `external_ai`                         |
| Professional Travel | Flights                   | `plane`                               |
| Professional Travel | Trains                    | `train`                               |
| Purchase            | Scientific equipment      | `scientific_equipment`                |
| Purchase            | IT equipment              | `it_equipment`                        |
| Purchase            | Consumables               | `consumable_accessories`              |
| Purchase            | Bio/chemical/gas products | `biological_chemical_gaseous_product` |
| Purchase            | Services                  | `services`                            |
| Purchase            | Vehicles                  | `vehicles`                            |
| Purchase            | Other purchases           | `other_purchases`                     |
| Purchase            | Additional purchases      | `additional_purchases`                |
| Research Facilities | Research facilities       | `research-facilities`                 |
| Research Facilities | Animal facilities         | `mice_and_fish_animal_facilities`     |
