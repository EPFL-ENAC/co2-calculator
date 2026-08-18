---
status: delivered
issue: 2170
last_updated: 2026-08-18
summary: EquipmentHandlerResponse.active_power_w/standby_power_w widened from int to float, matching the equipment_factors.csv contract and fixing a 500 on fractional power values.
---

# 2170 — Equipment response power fields: int → float

## Problem

`equipment_factors.csv` moved `active_power_w` / `standby_power_w` from
`int` to `float` (data-description doc, Equipment section) ~4 weeks before
this fix. `EquipmentFactorCreate` / `Update` / `Response` were updated at
the time; `EquipmentHandlerResponse` in
`app/modules/equipment/data_entries.py` was not. Any data entry enriched
with a fractional factor value 500s at `to_response()` — reproduced in
stage on entry id=385685 (`standby_power_w=2.368421053`).

## Fix

Two-field type change, `int | None` → `float | None`, on
`EquipmentHandlerResponse`. No other equipment DTO needed touching — the
factor-side DTOs, the formula (`handlers.py`, already casts via `float()`),
and the frontend (TS `number`, no int assumption) were already correct.

## Regression

`tests/unit/modules/test_equipment_schemas.py::test_equipment_response_accepts_fractional_power_w`
validates `EquipmentHandlerResponse` against the exact stage payload;
confirmed failing pre-fix with the reported `int_from_float` error,
passing post-fix.
