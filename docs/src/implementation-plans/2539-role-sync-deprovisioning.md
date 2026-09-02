---
status: in-progress
issue: 2539
last_updated: 2026-09-02
summary: "Give role sync a real deprovisioning story: two-strikes
  confirmation before an empty response ever revokes, backoff on repeated
  skips, a configurable sync TTL, and an admin-only force-revoke endpoint."
---

# 2539 — Role sync deprovisioning story

## Context

[#2538](https://github.com/EPFL-ENAC/co2-calculator/pull/2538) (issue #2531)
stopped background role sync from wiping a user's roles on an ambiguous
empty Accred response. Correct, but it means the automatic path can no
longer revoke anything at all — revocation only happens at the user's next
**login**, which has no guard (`UserService.upsert_user` writes whatever
the provider returns). That bounds the exposure to the refresh-token
lifetime (12h dev / 24h default) rather than being indefinite, but it is
still not a deprovisioning story: nothing shrinks a session's authority
before the user re-authenticates.

This issue closes that gap without reopening the wipe #2538 just closed.

## What shipped

### 1. Configurable sync TTL (`app/core/config.py`)

`Settings.ROLE_SYNC_TTL_MINUTES` (default `60`) replaces a hardcoded
`sync_ttl_minutes: int = 15` constructor default that had no env knob,
unlike `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_HOURS` next to
it conceptually. `POST /v1/session` only refreshes reactively on a 401, so a
refresh is already spaced by the access-token TTL — always well above the
old 15 minutes in every configured environment, meaning the TTL gate almost
never actually throttled anything. 1h keeps a mid-session role grant landing
the same session without re-hitting Accred on every refresh. Wired into
`RoleSyncService` at its one call site, `role_sync_tasks.py`.

### 2. Backoff on every skip (`app/services/role_sync_service.py`)

Before, a skip (network error or suspicious-empty) left `last_roles_sync_at`
untouched, so the TTL gate never engaged for the _next_ attempt — a burst of
near-simultaneous calls (multiple tabs 401ing together, or a fleet-wide
Accred outage hitting many users' natural refresh at once) re-hit the
provider with zero rate limit. Both skip branches now stamp the timestamp
too, so the next attempt waits one TTL period — the same backoff the
success path already had. Flat, not escalating: matches "a short backoff",
not a new exponential-backoff subsystem.

### 3. Two-strikes confirmation (`RoleSyncService._handle_suspicious_empty`)

The general mechanism from the issue discussion. A nullable
`users.roles_empty_since` timestamp:

- Set on the **first** empty response for a user who has roles (cleared by
  the caller on any non-empty result, including a no-change match — a stale
  first-seen time must not survive to poison a later, unrelated empty
  response).
- A **second** empty response, confirmed `2 * ROLE_SYNC_TTL_MINUTES` after
  the first, is what a genuine revocation looks like — this is the only
  path that can now revoke without a login. It applies for real:
  `roles = []`, logged at ERROR.
- Anything short of that stays a no-op, matching #2531's invariant that a
  single ambiguous response can never destroy authority.

### 4. Admin-triggered force revoke (`app/api/v1/users.py`)

`POST /v1/users/{user_id}/revoke-roles`, gated by
`require_permission("backoffice.users", "edit")` — the first implementation
of the long-documented-but-never-built `backoffice.users` permission (see
`app.main`'s API description, and the file's own former docstring: "kept
for potential future internal user management needs").

Reinstates the exact `force` hatch declined in #2538's review
(`if not new_roles and old_roles and not force:`), but reachable only from
this endpoint — never from the automatic `/v1/session` path, which always
passes `force=False`. It re-runs the provider check right now, skipping
both the TTL gate and the two-strikes guard, and applies whatever comes
back — including empty. It does not invent a revocation the provider
doesn't confirm: if Accred still reports the user's roles, nothing changes
(`outcome: no_change`). A `JwtClaimsRoleProvider` user 400s — there is no
out-of-band source to re-check for them.

### 5. Metric on every skip (shared with #2623)

`role_sync.skipped` (→ `role_sync_skipped_total{outcome=...}` in
Prometheus) is incremented on `skipped_suspicious_empty` and
`skipped_provider_unavailable`, mirroring `app/db.py`'s existing
`db.pool.timeouts` / `db.connect.failures` counter pattern. See
[#2623](https://github.com/EPFL-ENAC/co2-calculator/issues/2623) for the
alert rule.

## Not built (deliberately)

- **`/persons/{id}`-absence fast path.** `AccredRoleProvider.get_user_by_user_id`
  already fetches `/persons/{id}`; a gone/inactive person record is a
  positive revocation signal and could skip the two-strikes wait. Called out
  in the issue discussion as an optimization on top of the mechanism above,
  not the mechanism itself — not built until the two-strikes window proves
  too slow in practice.
- **Admin frontend for the revoke endpoint.** The backend action exists;
  there is no UI for a super admin to call it. Today it is reachable only
  via the API directly (Swagger, `curl`, etc.), which is not a usable
  day-to-day workflow. Tracked as a follow-up — see
  [#2539](https://github.com/EPFL-ENAC/co2-calculator/issues/2539), needs a
  small backoffice page/action wired to `POST /v1/users/{user_id}/revoke-roles`
  under the same `backoffice.users` permission before this is actually
  usable by anyone but a developer.

## Regression tests

`backend/tests/unit/services/test_role_sync_service.py`:

| Test                                                          | Pins                                                    |
| ------------------------------------------------------------- | ------------------------------------------------------- |
| `test_suspicious_empty_engages_backoff_for_immediate_retries` | a near-simultaneous retry is TTL-gated, not instant     |
| `test_suspicious_empty_still_retries_once_the_ttl_elapses`    | the backoff is one TTL period, not permanent            |
| `test_first_strike_records_when_it_started_without_wiping`    | strike one never wipes                                  |
| `test_second_strike_within_the_window_still_does_not_wipe`    | strike two too soon is still a blip                     |
| `test_second_strike_past_the_window_applies_the_revocation`   | confirmed twice, 2x TTL apart, applies for real         |
| `test_recovering_to_the_same_roles_clears_a_pending_strike`   | a matching non-empty result clears the timer            |
| `test_force_bypasses_the_guard_for_admin_revoke`              | the admin path's whole mechanism                        |
| `test_force_does_not_revoke_when_accred_still_reports_roles`  | force never fabricates a revocation                     |
| `test_provider_network_error_skips_without_touching_roles`    | updated: now asserts the backoff stamp, not its absence |

`backend/tests/integration/v1/test_users_revoke_roles.py` (new): permission
gate (403 without `backoffice.users.edit`, 404 unknown user), the endpoint
actually applying an empty result, not fabricating one when Accred still
reports roles, and the 400 for a provider with no out-of-band source.

## Migration

`4e24903124ff_add_roles_empty_since_for_two_strikes_.py` — adds
`users.roles_empty_since` (nullable timestamp, no index — always queried by
PK). Generated via `make db-revision`; one unrelated false-positive
`drop_index` on `ix_classification_translations_label_trgm` pruned (pre-existing
model/DB drift, not part of this change).

## Docs

`docs/src/architecture/04-auth-flow.md` §6a documents the whole background
sync mechanism (TTL, backoff, two-strikes, force) for anyone reading the
auth flow cold.
