---
status: delivered
issue: 862
last_updated: 2026-06-03
title: "Backoffice affiliation scope by unit subtree (cf-anchored, intersection clamp)"
summary: "Resolve backoffice.reporting affiliation scope from a single ACCRED unit cf (any level) into a descendant unit-id set via path_institutional_code, and clamp every backoffice query by intersecting the scope set with the endpoint filter set. Replaces path_name substring matching and list-narrowing."
---

## Context

`backoffice.reporting` is affiliation-scoped for the metier role and global for
superadmin. The scope token now comes straight from ACCRED as the authorized
unit's **cf** (`institutional_id`) at **any** hierarchy level — see
[role-scope-explicit-own-unit](role-scope-explicit-own-unit.md) and
[862-backoffice-update-permissions](862-backoffice-update-permissions.md). For
example cf `12000` is ENAC, sitting in path `EPFL ENAC ENAC-SG ENAC-IT4R`.

Two defects motivated this plan:

1. **Scope never resolves to units.** The reporting query resolves the
   affiliation filter through `_get_selected_units` (matches `Unit.name`/`Unit.id`),
   but the scope token is a cf. The TEST fixtures made this invisible:
   `TEST_AFFILIATION = "testaffiliation"` matches no unit name _or_ path, so a
   backoffice_metier user sees an empty reporting page. No test exercised the
   scope-token → units path positively, so nothing caught it.
2. **Wrong composition.** Filters were OR'd and scope was applied by narrowing
   the affiliation _list_ (`narrow_path_affiliation`), not by intersecting unit
   sets. A scoped caller could request a lvl4 unit outside their subtree and
   still get rows.

## Target model

### Scope resolution (cf → subtree)

The scope token is a `Unit.institutional_id` (cf). Resolve it to a concrete
unit-id set:

1. `institutional_code(s) ← SELECT institutional_code WHERE institutional_id IN tokens`
2. `scope_set ← unit ids whose path_institutional_code token-matches any code (incl. self)`

`path_institutional_code` is the indexed, self-inclusive query path
(`" ".join(ancestors + [self])`); `path_institutional_id` (cf path) is nullable
and "not queried" — do **not** match on it. This reuses the existing
token-boundary matching in `_get_descendant_unit_ids`; only the resolver
(cf → code, vs name/id → code) is new.

Scope is "a unit at any level," full stop. There is no fixed affiliation level.
`AFFILIATION_LEVEL` and the sortpath-splitting block in `role_provider.py` are
**dead** and removed.

### Composition (the security invariant)

```
filter_set = descendants(path_affiliation) ∪ direct(path_lvl4)   # None if no endpoint filters
scope_set  = descendants(scope cf tokens)                        # for scoped callers
```

| Caller              | Endpoint filters | Effective unit-id set    |
| ------------------- | ---------------- | ------------------------ |
| global (superadmin) | none             | `None` → all units       |
| global              | present          | `filter_set`             |
| scoped (metier)     | none             | `scope_set`              |
| scoped              | present          | `scope_set ∩ filter_set` |

**Invariant:** a scoped caller never resolves to `None`. `None` means "no
constraint" and would leak all units; a scoped caller must always produce a
concrete set (possibly empty). `set()` flows to `WHERE id IN ()` → zero rows.
Filters keep OR semantics among themselves; the scope is an AND clamp on top —
matching `scope ∩ ((aff_A ∪ aff_B) ∪ (lvl4_X ∪ lvl4_Y))`.

### Dropdowns (UX, not security)

`/affiliations` and `/units` lists show, for a scoped caller, only units within
the scope subtree (descendants-or-self of the scope unit), filtered to lvl2/3
for `/affiliations`. If the scope is lvl4, `/affiliations` is empty — acceptable,
since the reporting clamp still exposes the unit's own data. Superadmin sees all.
This replaces the `path_name` ILIKE predicate with a `path_institutional_code`
subtree predicate derived from the scope cf(s).

## Touchpoints (each staged with a test)

| File                                                                    | Change                                                                                                                                                                                                          |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/providers/role_provider.py`                                        | Remove dead `AFFILIATION_LEVEL` + commented sortpath block; keep `AffiliationScope(affiliation=cf)`                                                                                                             |
| `app/repositories/carbon_report_module_repo.py`                         | New cf→subtree scope resolver; `_resolve_hierarchy_unit_ids` takes scope and applies `scope_set ∩ filter_set` with the invariant above                                                                          |
| `app/utils/scoping.py`                                                  | Add code-subtree predicate from scope cf(s); remove `build_affiliation_predicate` (path_name) and `narrow_path_affiliation` once call sites migrate                                                             |
| `app/api/v1/backoffice.py` (×3: `/units`, usage export, results export) | Pass `is_global` + scope cf(s) to the repo clamp; drop `narrow_path_affiliation`                                                                                                                                |
| `app/api/v1/backoffice_reporting.py` (×2: `/affiliations`, `/units`)    | Replace `build_affiliation_predicate` with the code-subtree predicate                                                                                                                                           |
| `app/providers/test_fixtures.py`                                        | Rebuild TEST_UNITS as a coherent hierarchy: an anchor unit with a cf, whose `institutional_code` appears as a token in its own and every descendant's `path_institutional_code`; `TEST_AFFILIATION` = anchor cf |

`gate_backoffice` / `derive_backoffice_affiliations` are unchanged — the cf is an
opaque sub-perimeter token in the `backoffice.reporting/<cf>` key.

## Tests

- **Fixture coherence:** `TEST_AFFILIATION` resolves to ≥1 TEST unit _by the rule
  the query uses_ (cf → code → `path_institutional_code` match). Fails today;
  would have caught the original bug.
- **Scope resolver:** cf token → expected descendant ids (incl. self) via
  `path_institutional_code`; cf with no matching unit → empty set (logged, not "all").
- **Invariant matrix (the regression guard):** the four rows above, asserting a
  scoped caller is never `None`; scoped + out-of-scope lvl4 filter → `{}`;
  superadmin + filters → `filter_set`; two affiliations in one facet → union.
- **Dropdown:** scoped caller sees only lvl2/3 within the scope subtree;
  superadmin sees all.
- **Endpoint integration:** real-DB E2E in `test_permission_scope_e2e.py` (seeded
  ENAC/STI subtrees) pin the route wiring — scoped caller sees only its subtree on
  `/backoffice-reporting/units`, `/affiliations`, and `/backoffice/years`;
  cross-affiliation scope → empty; superadmin → all. (Replaced the prior
  SQL-string-emulation mocks, which tested the mock, not the query.)

## Out of scope

Role rename (`calco2.superadmin` → `calco2.backoffice.admin`) and the broader
page-driven permission shape, both covered by
[862-backoffice-update-permissions](862-backoffice-update-permissions.md).
