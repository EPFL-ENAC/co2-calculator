---
status: in-progress
issue: 2531
last_updated: 2026-08-30
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
in a FastAPI `BackgroundTask` fired by `/v1/session`, so the request that
caused the damage succeeded — the symptom appeared later, on a different
request, with no error anywhere.

An empty read from an external system is ambiguous. Treating it as fact
manufactures a claim ("this user has zero roles") from an absence of data and
then persists it. That is the no-silent-fallbacks invariant seen from the
other side.

## What shipped

### 1. Guard the wipe (`app/services/role_sync_service.py`)

If the provider returns no roles while the user has some, the sync keeps the
stored roles, does **not** stamp `last_roles_sync_at` (so the next call
retries rather than believing it succeeded), and logs at ERROR. Empty-in /
empty-out for a user who genuinely has no roles still settles normally, so
role-less users do not spin.

### 2. Provider failures raise instead of returning empty
(`app/providers/role_provider.py`)

- Unconfigured Accred credentials raised `RoleProviderNetworkError` instead
  of `return []` / `return {}` — one pod with rotated credentials could
  otherwise wipe every user it served.
- **Wholesale drop detection**: the mapping loop skips an authorization on
  four conditions, and an Accred response-shape change trips them all at
  once (the schema has already moved once — `resource.cf` →
  `resource.altname`). When Accred returns authorizations and none map to a
  role, that is a contract break, not a user without roles: the provider logs
  the offending payload's keys — which names the field that moved — and
  raises.

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

## Regression tests

| Test | Pins |
| --- | --- |
| `test_empty_provider_response_does_not_wipe_existing_roles` | the wipe itself |
| `test_suspicious_empty_leaves_sync_timestamp_untouched` | the next sync retries |
| `test_non_empty_role_change_still_applies` | the guard does not freeze roles |
| `test_user_with_no_roles_receiving_no_roles_is_not_an_error` | no retry loop for role-less users |
| `test_provider_network_error_skips_without_touching_roles` | abort path writes nothing |
| `test_login_stamps_sync_time_so_next_session_call_is_ttl_gated` | login stamps freshness |
| `test_accred_unconfigured_raises_on_get_roles_by_user_id` / `..._get_user_by_user_id` | unconfigured raises |
| `test_accred_raises_when_every_authorization_is_dropped` | schema move fails loudly |
| `test_role_name_prefix_matches_every_role_name` / `test_accred_query_uses_role_name_prefix` | filter cannot drift from the enum |

`tests/unit/tasks/test_role_sync_skip.py` (the `JwtClaimsRoleProvider`
background-sync opt-out from #2526) still passes unchanged.

## Open questions for the maintainer

**1. There is no longer any path that empties a user's roles.** The guard
fires on exactly the shape a genuine full revocation has (person leaves, last
accreditation expires → `authorizations: []`), so that user keeps their access
until someone reads the ERROR log. `force=True` only skips the TTL gate, not
the guard. This is what the issue asks for — an empty response may not shrink
authority unless the provider positively confirms it, and it cannot. Partial
revocations (any non-empty smaller set) still apply normally, so only the
all-roles-removed case sticks.

If a deprovisioning path is wanted, the ready-made hatch is one line —
`if not new_roles and old_roles and not force:` — which makes an
admin-triggered forced sync able to empty roles while the automatic
`/v1/session` sync (the only production caller, always `force=False`) stays
guarded. Not implemented here: nothing calls `force=True` in production today,
and the choice belongs to the maintainer.

**2. No backoff on the retry.** Not stamping `last_roles_sync_at` on the skip
paths is what makes the next sync retry, but it also removes the TTL backoff
for exactly the users who are failing. If the cause is fleet-wide (an Accred
schema change), every `/v1/session` from every user re-hits Accred with no
rate limit for as long as it lasts. Deliberate trade of provider load for
recovery latency; worth revisiting if the ERROR logs ever show it sustained.

**3. The drop detection hardens a soft failure into a hard one.** A user
holding only a `calco2.*` authorization that is not yet in `RoleName` (a new
role rolled out in Accred before the code supports it) now gets a 503 at login
instead of logging in with zero roles. Both outcomes are wrong; failing loudly
is the one that gets noticed and fixed. Narrowing it to "every authorization
had a recognized name but was dropped later in the loop" would isolate the
schema-move case from the unknown-role case if that trade is not wanted.

## Not in scope

`AccredRoleProvider.get_roles`'s `except ValueError: return []` is a surviving
silent fallback in the same file (missing `uniqueid` in userinfo). Left alone —
it belongs to the login path, not the sync path.
