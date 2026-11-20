---
status: delivered
issue: none (code-scanning alerts 1377, 1378, 1382)
last_updated: 2026-11-20
summary: The item routes of a data entry get the traveler filter of the travel lists. A standard user can then not touch the trip of another traveler. External cloud and AI stays visible to the whole unit.
---

# Own scope on the data entry item routes

This plan closes a gap in permission scoping. The guardrails require a
plan that both maintainers review before the code changes. Branch
`fix/code-scanning-llm-audit`.

## The rule

The maintainer decided this rule on 2026-11-19.

| Module                           | A standard user sees and edits            |
| -------------------------------- | ----------------------------------------- |
| Professional travel              | the trips where they are the traveler     |
| External cloud and AI            | every row of the unit, by design          |
| Any module in an Explore sandbox | every row, because the sandbox is private |

A traveler match compares `data["user_institutional_id"]` with the
`institutional_id` of the user. The travel lists and the trips map
already apply this rule. It is not a `created_by` match.

## The defect

The list routes filter the travel rows. The item routes do not.

- `GET`, `PATCH` and `DELETE` on one entry
  (`backend/app/api/v1/carbon_report_module.py`, about line 1001) load the
  row with `DataEntryRepository.get_in_module`. That query filters on the
  id, the module and the entry type only.
- The ids are sequential. If a standard user sends the id of a
  colleague's trip in the same unit, they can read, change or delete it.

## The change

1. `get_in_module` takes an optional `institutional_id_filter`. If it is
   set, the query adds the traveler clause that the list query uses
   (`data_entry_repo.py`, about line 1785).
2. `DataEntryService.get` and `CarbonReportModuleWorkflow._get_entry`
   pass the filter on.
3. The three item routes compute the filter with
   `_get_professional_travel_institutional_id_filter`, the same call as
   the list route. The function returns `None` for principals, for
   external cloud and AI, and for Explore sandboxes.
4. A row that does not match returns 404, the same answer as a row that
   does not exist. A caller cannot probe for ids.

The change adds no permission key and no role.

## Tests

Extend `backend/tests/unit/v1/test_travel_table_visibility.py`:

- A standard user gets 404 on `GET`, `PATCH` and `DELETE` of a trip
  whose traveler is another user. The row stays unchanged.
- The same user gets 200 on their own trip.
- A principal of the unit gets 200 on both trips.
- A standard user still gets 200 on an external cloud and AI row that a
  colleague created.

## Documentation

`docs/src/backend/06-PERMISSION-SYSTEM.md` states the rule of the table
above. Before this plan, the page said "Own: see only records the user
created", which no code applies.

## Out of scope

- `DataEntryRepository.update` takes a `user_id` that it does not read.
  The ownership check belongs on the load, so this plan does not use it.
- Alert 1379, the Active toggle, is a separate commit on the same branch.

## What shipped

The maintainer approved the plan on 2026-11-20. The change follows it.
The repository has one spelling of the traveler clause, `_traveler_is`,
for the list and the item query. The GET item route is now 44 lines.
The PATCH and DELETE routes were already over the limit of 40 lines.

## Subsequent step

Run the audit again on the branch. If it still flags external cloud and
AI, an owner filter on `created_by_id` is the only change that removes
the finding.
