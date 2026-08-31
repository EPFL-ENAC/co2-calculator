# GitHub Project Board

[Project 40 — Calculator CO2](https://github.com/orgs/EPFL-ENAC/projects/40)
is where the work is tracked. This page is the field reference: what each
column means, which values are live, and which are dead weight. Code rules
live in [`guardrails.md`](./guardrails.md).

Snapshot: 2026-08-31 — 811 items, 19 fields, 13 views, public.
Project ID `PVT_kwDOA62qLM4BE4-5`.

## Fields

| Field                                                                                                           | Type          | Values                                                                                                                                          | Items set |
| --------------------------------------------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| Status                                                                                                          | single-select | Backlog → Comité Spécialisé → Ready → In progress → In review → Ready for validation → QA Validation → Tests Metier → Validated                 | 770       |
| Priority                                                                                                        | single-select | P0, P1, P2, P3                                                                                                                                  | 496       |
| Sprint                                                                                                          | iteration     | 14 days, Monday start                                                                                                                           | 696       |
| Est. hours                                                                                                      | number        | 0.5 / 1 / 2 / 3 / 4 / 6 / 8 / 16 ladder                                                                                                         | 382       |
| Category                                                                                                        | single-select | FEAT, TASK, SPECS, DESIGN, DOC, TEXT, FIX, DATA                                                                                                 | 250       |
| Module                                                                                                          | single-select | Purchases, Headcount, Travel, Research facilities, ExternalCloudsAI, Equipments, Processes, Buildings, Generic, BackOffice, Results, Simulation | 249       |
| Size                                                                                                            | single-select | XS, S, M, L, XL — **dead**, use Est. hours                                                                                                      | 16        |
| Assignees, Labels, Linked PRs, Reviewers, Repository, Parent issue, Sub-issues progress, Created/Updated/Closed | built-in      |                                                                                                                                                 | —         |
| Milestone                                                                                                       | built-in      | **never used**                                                                                                                                  | 0         |

Two repositories feed the board: `co2-calculator` (808 items) and
`co2-calculator-back-office-doc` (3).

## Status flow

`Backlog` and `Comité Spécialisé` hold unrefined work — the latter is for
items needing a business-committee decision. `Ready` means specced and
estimated. After `In review` (code review), an item goes to
`Ready for validation`, then `QA Validation` (IT4R), then `Tests Metier`
(business testing), then `Validated`.

| Status               | Items |     | Priority  | Items |
| -------------------- | ----: | --- | --------- | ----: |
| Validated            |   720 |     | P0        |   202 |
| _(empty)_            |    41 |     | P3        |   111 |
| Ready                |    12 |     | P1        |   106 |
| Ready for validation |    12 |     | P2        |    77 |
| QA Validation        |    12 |     | _(empty)_ |   315 |
| Backlog              |     5 |     |           |       |
| In progress          |     3 |     |           |       |
| Tests Metier         |     3 |     |           |       |
| In review            |     2 |     |           |       |
| Comité Spécialisé    |     1 |     |           |       |

Category and Module are set on roughly a third of items — Module is the
useful one for cross-cutting queries (Results 52, BackOffice 50, Generic 38,
Travel 27, Equipments 25, Headcount 16, ExternalCloudsAI 11, Buildings 11,
Purchases 8, Processes 5, Research facilities 4, Simulation 2).

## Sprints

Cadence settled at exactly 14 days from Sprint 8 onward; earlier sprints ran
16–32 days.

| Sprint                          | Start      | Days | Items |
| ------------------------------- | ---------- | ---: | ----: |
| Post-delivery                   | 2026-09-07 |   14 |    23 |
| Delivery                        | 2026-08-24 |   14 |    93 |
| Simulator Sprint 3 (QA & Fixes) | 2026-08-10 |   14 |    74 |
| Simulator Sprint 2              | 2026-07-27 |   14 |    29 |
| Simulator Sprint 1              | 2026-07-13 |   14 |    15 |
| Sprint de Refactor              | 2026-06-29 |   14 |    55 |
| Delivery v1.0 & Hot fixes       | 2026-06-17 |   12 |    15 |
| Sprint 12 (QA & Fixes)          | 2026-06-03 |   14 |    72 |
| Sprint 11 (QA & Fixes)          | 2026-05-20 |   14 |    46 |
| Sprint 10                       | 2026-05-05 |   15 |    54 |
| Sprint 9                        | 2026-04-14 |   21 |    31 |
| Sprint 8                        | 2026-03-31 |   14 |    26 |
| Sprint 7                        | 2026-03-10 |   21 |    27 |
| Sprint 6                        | 2026-02-11 |   27 |    25 |
| Sprint 5                        | 2026-01-20 |   22 |    16 |
| Sprint 4                        | 2025-12-19 |   32 |    21 |
| Sprint 3                        | 2025-12-03 |   16 |    19 |
| Sprint 2                        | 2025-11-19 |   14 |    26 |
| S1 - Set up                     | 2025-10-27 |   23 |    28 |
| Preliminary work (S0)           | 2025-10-19 |    8 |     — |

115 items carry no sprint.

## Labels

Type labels double as branch prefixes — `bug` → `fix/`, `feat` → `feat/`,
and so on. The MoSCoW set (Must have / Should have / nice to have) is
orthogonal to the Priority field and predates it.

| Label                                               | Purpose                                                | Used |
| --------------------------------------------------- | ------------------------------------------------------ | ---: |
| `bug`                                               | Something isn't working — branch `fix/`                |  165 |
| `Must have`                                         | MoSCoW                                                 |   87 |
| `nice to have`                                      | MoSCoW                                                 |   55 |
| `Should have`                                       | MoSCoW                                                 |   26 |
| `non-conforme`                                      | QA: shipped behaviour doesn't match spec               |   26 |
| `feat`                                              | New feature — branch `feat/`                           |   21 |
| `issue in definition`                               | Draft issue, specs being clarified                     |   15 |
| `refactor`                                          | Branch `refactor/`                                     |    7 |
| `Cannot reproduce`                                  | QA outcome                                             |    6 |
| `Blocking`                                          | Blocking for tests, needed ASAP                        |    4 |
| `docs`                                              | Branch `docs/`                                         |    3 |
| `perf`                                              | Branch `perf/`                                         |    2 |
| `python`, `javascript`, `python:uv`, `dependencies` | Dependabot area tags                                   |    2 |
| `wontfix`                                           | Won't be worked on                                     |    1 |
| `polish`                                            | UI/UX/phrasing cleanup under 30 min — branch `polish/` |    0 |
| `style`, `test`                                     | Branches `style/`, `test/`                             |    0 |
| `Comité`                                            | À rediscuter en comité                                 |    0 |
| `ai-review`                                         | Flagged for AI review                                  |    0 |
| `autorelease: pending`, `autorelease: tagged`       | release-please automation                              |    0 |

## Views

| #   | Name                | Layout  | Filter                                                           | Group / sort                  |
| --- | ------------------- | ------- | ---------------------------------------------------------------- | ----------------------------- |
| 1   | Current sprint dev  | board   | `sprint:@current -title:*spec*`                                  | —                             |
| 2   | Next sprint         | board   | `sprint:@next assignee:BenBotros`                                | —                             |
| 3   | Prioritized backlog | table   | `is:open`                                                        | Sprint / Priority ↑           |
| 4   | Roadmap             | roadmap | —                                                                | —                             |
| 5   | In review           | table   | `status:"In review"`                                             | —                             |
| 6   | My items            | table   | `assignee:@me`                                                   | —                             |
| 7   | Everything          | table   | `is:open`                                                        | Sprint / Priority ↑, Status ↓ |
| 8   | Pour Agnès          | table   | `assignee:agletiec -status:Validated`                            | Sprint                        |
| 10  | Previous sprint     | board   | `sprint:@previous`                                               | —                             |
| 11  | Specs progress      | board   | `specs`                                                          | Sprint ↑                      |
| 12  | QA                  | table   | `status:"QA Validation"`                                         | Sprint                        |
| 14  | Vue de Caro         | board   | `is:open` minus sprints S0 → Sprint 6                            | Sprint                        |
| 15  | VueCaro             | board   | `-status:"Ready for validation","In progress",Ready,"In review"` | —                             |

## Automations

Four built-in workflows, all enabled: **Item closed**, **Pull request
merged**, **Auto-close issue**, **Auto-add sub-issues to project**. Opening a
sub-issue therefore puts it on the board without anyone touching it.

## Rough edges

- **Module has two `Generic` options** (`48fab104`, `d7efe70b`) — the same
  bucket silently split in two. Merge them.
- **Size is dead** (16 of 811 items); Est. hours replaced it. Delete the field.
- **Views 14 and 15** are near-duplicates, and view 14's filter hardcodes a
  sprint denylist that needs hand-editing every sprint. A
  `-sprint:@previous`-style filter or a status filter would self-maintain.

## Querying the board

```bash
gh project view 40 --owner EPFL-ENAC --format json
gh project field-list 40 --owner EPFL-ENAC --format json
gh project item-list 40 --owner EPFL-ENAC --limit 1000 --format json
```

Iteration dates, view filters, and automations are GraphQL-only:

```bash
gh api graphql -f query='query{organization(login:"EPFL-ENAC"){projectV2(number:40){
  field(name:"Sprint"){... on ProjectV2IterationField{configuration{
    iterations{title startDate duration}
    completedIterations{title startDate duration}}}}
  views(first:30){nodes{number name layout filter}}
  workflows(first:30){nodes{name enabled}}}}}'
```
