---
status: delivered
issue: 2404
last_updated: 2026-08-27
title: "Page-first pagination for the submodule listing"
summary: "get_submodule_data joined per-row factor resolution and the module's whole emission aggregate before applying LIMIT, so a 20-row page paid a module-sized cost (measured 18,620 of 20,912 buffers on discarded rows). When sort/filter read nothing outside data_entries, the repo now resolves the page's ids first and restricts both expensive branches to them, making cost proportional to the page instead of the module. Falls back to the original shape whenever eligibility isn't provable, so results cannot diverge -- only cost can."
---

# Page-first pagination for the submodule listing (#2404 follow-up)

Named as the structural follow-up in
[2404-factor-resolution-indexes.md](2404-factor-resolution-indexes.md): the
indexes there harden the factor-resolution branch, but the EXPLAINs on the
issue showed the _dominant_ cost is the emission aggregate, which touches
every entry in the module to serve one page.

## What changed

`DataEntryRepository.get_submodule_data`: when the requested sort/filter can
be decided from `data_entries` alone (`_page_first_eligible`), the page's
entry ids are resolved first (`_page_first_entry_ids`) and both the emission
aggregate and the per-row factor-resolution join are restricted to just
those ids instead of the whole module.

Ineligible whenever sort or filter reads something outside `data_entries` —
`kg_co2eq` (backed by the emission aggregate), a factor-backed sort/filter
column (detected the same way the existing count-query join guard already
does, by string-matching the rendered SQLAlchemy expression for `factors`/
`building_rooms`), or a handler `default_where` referencing either. Travel,
buildings and headcount entries keep their existing shape unconditionally —
their sorts read joined entities the ids-only query has no way to reproduce.

## Why results cannot diverge

Both paths call the **same** `_resolved_factor_id` subquery and the **same**
emission-aggregate query shape — page-first only adds an `id IN (...)`
restriction to each. There is no second resolution implementation to drift.
`test_page_first_equals_full_shape_across_pages` and
`..._with_filter` assert byte-identical `SubmoduleResponse` output (items,
order, kg totals, resolved factor) between the page-first path and the
original shape forced on, across an offset boundary — the case where a
double-applied offset would silently return an empty or wrong page while
every same-page test stayed green.

`test_page_first_actually_engages` guards against the eligibility gate
silently going dead (returning `None` for a call that should qualify), which
would make every equivalence test above pass vacuously.

## Deliberately not changed

- Travel/buildings/headcount branches, and any handler `default_where` or
  filter reading `Factor`/`BuildingRoom` — not touched, not optimized.
- The count query's own conditional factor-join logic (already page-scoped
  correctly) — untouched.
