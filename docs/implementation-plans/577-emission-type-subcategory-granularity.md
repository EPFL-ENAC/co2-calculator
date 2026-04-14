# Emission Type Subcategory Granularity

## Context

The current EmissionType hierarchy for Buildings is not granular enough. It needs a **ZZ item level** (room type) beneath each YY subcategory (energy type). Purchases also needs a new category.

## 1. Buildings — Target Structure

### Rooms (XX = existing `buildings__rooms`)

Each YY subcategory gains ZZ items for room type:

| YY Subcategory     | Scope | ZZ Items                                                              |
| ------------------ | ----- | --------------------------------------------------------------------- |
| lighting           | 2     | office, laboratories, archives, libraries, auditoriums, miscellaneous |
| cooling            | 2     | office, laboratories, archives, libraries, auditoriums, miscellaneous |
| ventilation        | 2     | office, laboratories, archives, libraries, auditoriums, miscellaneous |
| heating, elec      | 2     | office, laboratories, archives, libraries, auditoriums, miscellaneous |
| heating, thermique | 1     | office, laboratories, archives, libraries, auditoriums, miscellaneous |

### Combustion (XX = existing `buildings__combustion`)

All subcategories are **scope 1**:

| YY Subcategory | Scope |
| -------------- | ----- |
| Natural gas    | 1     |
| Heating oil    | 1     |
| Biomethane     | 1     |
| Pellets        | 1     |
| Forest chips   | 1     |
| Wood logs      | 1     |

## 2. Purchases — New Category

- Add a new category **Additional Purchases** with a subcategory of **LN2**

## 3. Requirements

- These changes should be reflected in stats and aggregated results
