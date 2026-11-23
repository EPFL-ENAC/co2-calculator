---
status: delivered
issue: 2160
last_updated: 2026-11-10
summary: "Two slow spots from prod traces: role sync now releases its DB connection before the EPFL API call, and the Explore print page no longer downloads the purchase taxonomy tree."
---

# #2160: role sync connection hold and the purchase taxonomy call

Prod traces from 2026-10-06 showed two slow spots. Both fixes ship in one PR.

## 1. Role sync held a DB transaction across the provider call

**Cause.** `RoleSyncService.sync_user_roles` loaded the user, which
autobegan a transaction. It then awaited
`role_provider.get_user_by_user_id` (the EPFL persons API, 10 s timeout)
with that transaction still open. Under prod's PgBouncer transaction
pooling, that pins one of the 70 server slots for the whole call. One
trace showed 3.1 s held on a 500 from the API.

**Fix.** After the TTL gate, the service rolls back, which returns the
connection. It calls the provider with no transaction open, then
re-fetches the user and writes in a short new transaction. Both callers
go through this method: the background task `trigger_role_sync_for_user`
and the admin route `revoke_user_roles`. Neither holds uncommitted writes
when it calls. The docstring says callers must not hand the session
uncommitted writes.

This uses rollback plus re-fetch, not the expunge plus rollback of
71b579a2a. A rollback expires loaded instances, so the service reloads
the user instead of reading expired attributes.

**Tests.** A fake provider records `session.in_transaction()` at call
time and the test asserts it was `False`. One test runs through the
task, one runs on the service directly. Both fail on the old code. The
service tests normalise SQLite's naive datetimes to UTC on reload, as
Postgres `timestamptz` does. The service now reloads by design, so the
two-strikes tests would otherwise compare naive and aware values.

## 2. Purchase taxonomy call on the Explore print page

**Cause.** #2391 moved purchase to a server-side typeahead.
`ModuleTable` and `ModuleForm` stopped downloading the ~17k-node UNSPSC
tree for `optionsSearch` kinds. The Explore print page
(`useSimulationExplorePrintData`) was missed. It still batch-fetched the
tree of every submodule with a `kind` field, which for purchase means
all eight.

**Fix.**

- `printTaxonomyEntries` in `utils/printTable.ts` leaves out
  `optionsSearch` kinds. Purchase now asks only for
  `purchases_centralized`.
- `renderPrintCell` falls back to the row's backend-resolved `labels`
  (#2401) when the tree has no entry. This is the same precedence
  `ModuleTable` uses.
- `fetchAllSubmoduleRows` sends `lang`. Without it, the rows endpoint
  defaults to English and a French report would print English
  descriptions.

**Numbers (local, ~3.7k purchase kinds; prod has ~17-20k).** These
measure the purchase batch call on the running dev backend.

| Request                        | Cold                            | Warm (median) | Size   |
| ------------------------------ | ------------------------------- | ------------- | ------ |
| Before: all 8 entries, `en`    | 0.40-0.58 s (2.68 s first ever) | 5 ms          | 216 KB |
| Before: all 8 entries, `fr`    | 0.43-0.63 s                     | 8 ms          | 220 KB |
| After: `purchases_centralized` | 8-17 ms                         | 4-5 ms        | 156 B  |

The cache is per pod, per language and per year, with a 1 h TTL, so
print requests in prod often hit a cold build. That fits the 1.4 s
trace. Warm calls were already cheap locally, so the gain is in cold
builds and payload size.

**Tests.** `print-table.spec.ts` covers the helper skipping an
`optionsSearch` submodule and the row-label fallback.
`print-rows-lang.spec.ts` checks that the rows request carries the
active `lang`. It mounts a harness, so it needs a browser.

## Not done

The tree builder itself was not tuned (linear kind lookup, per-response
validation). Nothing requests the big purchase trees any more, so that
work would be speculative.
