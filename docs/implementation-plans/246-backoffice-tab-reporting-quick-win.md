## 🔍 Filters

### General behavior

- [ ] ⭐ Search function available across filters
- [ ] Filters apply instantly to the table and exports

### Module completion filter

- [x] ⭐ For each module, status options:
  - `Not started` (replaces `0` / default)
  - `In progress` (replaces `1`)
  - `Validated` (replaces `2`)
- [ ] ⭐ Collapsible display to reduce vertical space for each module

## 💾 Units Table

### General behavior

- [ ] Displays the list of units resulting from applied filters
- [ ] Table is scrollable
- [x] Pagination enabled
  - Default: 10 units per page
  - Option to display all rows
- [ ] Each column is sortable
- [ ] Search applies to table content
- [ ] If multiple years are selected:
  - `Validation status` displays the number of validated years

### Columns (order matters)

2. [ ] ⭐ **Affiliation**
   - EN: Affiliation
   - FR: Affiliation
   - Displays "Affiliation" tel que dans le filtre

3. [ ] ⭐ **Highest result category** (REMOVE "Module " sed, display just module key)
   - EN: Highest result category
   - FR: Catégorie de résultat le plus élevé
   - Displays the module name that is: validated AND has the highest tCo2-eq result.

4. [ ] ⭐ **View**
   - Eye icon
   - Opens the Results page of the selected unit - in a new tab.
   - Visualization restricted by role and accreditation.

- [ ] Rename table action:
  - From: `View all`
  - To: `View full table`
    => CANCELED.

## 📦 ⭐ Usage Statistics Box

Placeholder for #461

## 📦 ⭐ Aggregated Results Box

Placeholder for #460

## ⬇️ Export Data

### General

- [ ] ⭐ Rename button:
  - From: `Export Report`
  - To: `Export data`

### Export types

- [ ] Options:
  - (1) `Results`
  - (2) `Details des données par modules` / ` DETAILED DATA PER MODULE`
  - (3) `Usage`
  - (4) `Combined`
