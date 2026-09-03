---
status: in-progress
issue: 2531
last_updated: 2026-09-02
summary: "Stop background role sync from erasing a user's roles when the
  role provider answers with an empty list, and make every way of getting
  that empty answer loud instead of silent."
---

# 2531 — Role sync must not read "I got nothing" as "there is nothing"

## The bug

`RoleSyncService.sync_user_roles` compared the provider's role list against
the stored one and wrote whatever came back. An empty provider response was
therefore persisted as `user.roles = []`, logged at INFO as
`User roles updated`, and the user 403'd on their next request. The sync runs
in a FastAPI `BackgroundTask` fired by `POST /v1/session` (token refresh, not
page load — `ADR-017` settled `GET /v1/session` as a pure DB read), so the
request that caused the damage succeeded — the symptom appeared later, on a
different request, with no error anywhere.

An empty read from an external system is ambiguous. Treating it as fact
manufactures a claim ("this user has zero roles") from an absence of data and
then persists it. That is the no-silent-fallbacks invariant seen from the
other side.

Leading hypothesis (issue discussion): the mapping loop in
`AccredRoleProvider.get_roles` drops an authorization on four conditions, an
Accred response-shape change trips all of them at once (the schema has moved
before — `resource.cf` → `resource.altname`), and a user with exactly one
authorization then maps to zero roles even though Accred returned data.

## What shipped

### 1. Guard the wipe (`app/services/role_sync_service.py`)

If the provider returns no roles while the user has some, the sync keeps the
stored roles, does **not** stamp `last_roles_sync_at` (so the next call
retries rather than believing it succeeded), and logs at ERROR. Empty-in /
empty-out for a user who genuinely has no roles still settles normally, so
role-less users do not spin.

### 2. Provider failures made loud, not silent (`app/providers/role_provider.py`)

- Unconfigured Accred credentials raise `RoleProviderNetworkError` instead of
  `return []` / `return {}` — one pod with rotated credentials could
  otherwise wipe every user it served.
- **Wholesale drop detection**: the mapping loop skips an authorization on
  four conditions, and an Accred response-shape change trips them all at
  once. When authorizations arrive and none map to a role, `_log_wholesale_drop`
  logs the offending payload's keys at ERROR — naming the field that moved —
  but deliberately does **not** raise. It raised in the first version of this
  fix (`_raise_on_wholesale_drop`); a required PR review finding reverted that
  (`f57eefaf4`) because `AccredRoleProvider.get_user_by_user_id` is also
  login's role-resolution call, so raising turned a user whose only
  authorization lacks `cf`/`altname` — this issue's own leading hypothesis —
  from "logs in with zero roles" into "permanently locked out behind a 503".
  Refusing to act on the resulting empty result is already §1's job
  (`RoleSyncService`'s wipe guard); this layer only has to make the cause
  visible.

### 3. Honest outcomes (`RoleSyncOutcome`)

`RoleSyncResult` now carries an outcome: `applied`, `no_change`,
`skipped_ttl`, `skipped_user_not_found`, `skipped_provider_unavailable`,
`skipped_suspicious_empty`. `sync_user_roles` catches
`RoleProviderNetworkError` and reports it as an outcome, so
`trigger_role_sync_for_user` logs one honest line instead of duplicating the
handling. Every `skipped_*` outcome writes nothing.

### 4. Login stamps `last_roles_sync_at` (`app/services/user_service.py`)

Login had just fetched authoritative roles from Accred but left the stale
timestamp, so the TTL gate was already expired and the very next
`/v1/session` re-synced — double provider load per login, and the wipe window
reopened seconds after a user recovered. `_upsert_user_identity` now stamps
the sync time whenever it stores provider-supplied roles.

### 5. One source of truth for the role namespace

`ROLE_NAME_PREFIX` is derived from `RoleName` in `app/models/user.py` and used
as the Accred `searchauthorization` filter. `calco2.` is the correct prefix;
the stale `co2.` references in comments, in `login_test`'s default parameter
(which yielded a user with **zero** roles), and in the OpenAPI description are
fixed. Hygiene, not the trigger.

### 6. Close the second wipe path (`app/repositories/user_repo.py`)

Found and fixed as a required PR review finding, in the same commit as §2's
revert (`f57eefaf4`). Unit sync reaches `bulk_upsert` through `map_api_user`,
which builds `User(**user_raw)`; `roles` is a property over `roles_raw`, so
the SQLModel constructor silently drops the `roles=` kwarg and leaves
`roles_raw` `None`. `session.merge()` copies every attribute, so persisting
that `None` overwrote the roles Accred had just resolved — a second wipe path
that §1's guard never covered, since it only guards the `/v1/session`
background-sync call, not unit sync. `bulk_upsert` now restores the existing
user's stored `roles_raw` whenever the incoming payload's is `None`; an
explicit empty list still clears, since that is a caller stating the user has
none.

## Regression tests

| Test                                                                                        | Pins                                |
| ------------------------------------------------------------------------------------------- | ----------------------------------- |
| `test_empty_provider_response_does_not_wipe_existing_roles`                                 | the wipe itself                     |
| `test_suspicious_empty_leaves_sync_timestamp_untouched`                                     | the next sync retries               |
| `test_non_empty_role_change_still_applies`                                                  | the guard does not freeze roles     |
| `test_user_with_no_roles_receiving_no_roles_is_not_an_error`                                | no retry loop for role-less users   |
| `test_provider_network_error_skips_without_touching_roles`                                  | abort path writes nothing           |
| `test_login_stamps_sync_time_so_next_session_call_is_ttl_gated`                             | login stamps freshness              |
| `test_accred_unconfigured_raises_on_get_roles_by_user_id` / `..._get_user_by_user_id`       | unconfigured raises                 |
| `test_accred_logs_but_does_not_raise_when_all_dropped`                                      | schema move is visible, not fatal   |
| `test_role_name_prefix_matches_every_role_name` / `test_accred_query_uses_role_name_prefix` | filter cannot drift from the enum   |
| `test_bulk_upsert_keeps_stored_roles_when_payload_carries_none`                             | the second wipe path                |
| `test_bulk_upsert_still_clears_roles_on_an_explicit_empty_list`                             | an explicit revocation still clears |
| `test_bulk_upsert_leaves_a_new_user_without_roles`                                          | a new user isn't defaulted          |

`tests/unit/tasks/test_role_sync_skip.py` (the `JwtClaimsRoleProvider`
background-sync opt-out from #2526) still passes unchanged.

## Maintainer decisions (resolved in PR review, 2026-08-30/31)

**1. The `force` escape hatch floated in the original draft of this plan is
declined.** It would reopen the exact failure mode this PR closes, and no
production caller passes `force=True` today. Deprovisioning is a separate
design, tracked in
[#2539](https://github.com/EPFL-ENAC/co2-calculator/issues/2539): a
two-strikes `roles_empty_since` timer (don't wipe on the first empty; believe
it on a second empty after 2× the sync TTL), an explicit admin revoke action
(the right home for a `force` that bypasses the guard, since human intent is
unambiguous where an empty API response is not), and an optional
`/persons/{id}`-absence fast path as an optimization on top of the timer.

**2. Corrected risk statement — revocation is not actually silenced.** An
earlier version of this plan (and the PR description) claimed a revoked user
"keeps access until someone reads the ERROR log". That is wrong:
`UserService.upsert_user` (the login path) has no guard — it writes whatever
role list the provider returns, including `[]`. A genuinely de-accredited
user loses access at their **next login**; this PR only stops the automatic
background sync from doing that destructively and without evidence. The
exposure window is bounded by the refresh-token lifetime — 12 h in
`backend/.env`, 24 h by config default — not indefinite, and not dependent on
anyone reading a log.

**3. No backoff on the retry.** Not stamping `last_roles_sync_at` on the skip
paths is what makes the next sync retry, but it also removes the TTL backoff
for exactly the users who are failing. If the cause is fleet-wide (an Accred
schema change), every `/v1/session` from every user re-hits Accred with no
rate limit for as long as it lasts. Deliberately deferred to
[#2539](https://github.com/EPFL-ENAC/co2-calculator/issues/2539) rather than
blocking this PR — carried over verbatim in that issue's body as "add a short
backoff on repeated skips before this reaches production".

**4. The drop-detection hardening question is resolved by §2 above.** A user
holding only an authorization that doesn't map (missing `cf`/`altname`, an
unrecognized role name) now logs in with zero roles again instead of hitting
a 503 — the soft failure this issue asked for, not a hard lockout.

## Not in scope

`AccredRoleProvider.get_roles`'s `except ValueError: return []` is a surviving
silent fallback in the same file (missing `uniqueid` in userinfo). Left alone —
it belongs to the login path, not the sync path.

Deprovisioning (making an empty response _eventually_ count as a real
revocation signal) is out of scope here by design — see
[#2539](https://github.com/EPFL-ENAC/co2-calculator/issues/2539).

Alerting on the guard firing is also out of scope here. The guard logs at
ERROR (§1, §2) but nothing counts or pages on it today — no metric, and no
backend error-tracking SDK (Sentry/GlitchTip is frontend-only). Filed
separately as [#2623](https://github.com/EPFL-ENAC/co2-calculator/issues/2623)
rather than folded into #2539, since it's an orthogonal observability gap
(make the existing log reach someone) independent of how deprovisioning is
eventually designed.

## Status

PR [#2538](https://github.com/EPFL-ENAC/co2-calculator/pull/2538): both
required review findings fixed (`f57eefaf4`), all CI checks green, mergeable.
Still open as a draft. Outstanding before merge:

- Un-draft.
- The PR description still carries the stale risk statement corrected in
  "Maintainer decisions" §2 above — reword before merge so the merged history
  doesn't preserve the wrong claim.
