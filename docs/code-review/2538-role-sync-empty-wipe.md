# Code review — PR #2538 `fix/2531-role-sync-empty-wipe`

**Reviewed:** `e948ecb5c` against `origin/dev` (`6bb8d284a`) · 2026-08-30
**Issue:** #2531 · **Follow-up already opened:** #2539

## Verdict: SHIP WITH FIXES

The central change — an empty provider response can no longer overwrite a
non-empty stored role set — is correct, minimal and well tested. Two things
must change before this reaches a deployed environment:

1. **R1** — change 3's `raise` turns a per-user data condition into a hard
   login failure. It can lock real users out with a misleading error, and it
   buys no protection the wipe guard does not already provide.
2. **R2** — the guard does not close every write path. `UserRepository.bulk_upsert`
   (the unit-sync ingestion job) still zeroes `roles_raw` on existing users,
   unguarded. The PR's headline invariant is not actually true repo-wide.

Everything else is either correct as shipped or a nit.

---

## The crux: does login still revoke? **Yes — the claim holds.**

Verified along the whole chain, not by inspection alone:

| Step                                                            | Evidence                                                                                                                                                 |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Genuine revocation reaches the provider as `authorizations: []` | `role_provider.py:591-595` returns `[]` **before** `_raise_on_wholesale_drop` is called (`:669`) — the drop guard is never consulted                     |
| `get_user_by_user_id` propagates that as `roles: []`            | `role_provider.py:499-502`                                                                                                                               |
| Login writes it                                                 | `auth.py:435` passes `provider_user.get("roles", [])` → `UserService.upsert_user` → `_upsert_user_identity` (`user_service.py:106`) → `user_repo.update` |
| `user_repo.update` has no guard                                 | `user_repo.py:121-122` — `if roles is not None: entity.roles = roles`. `[]` is not `None`, so `[]` is written                                            |

Confirmed empirically with a throwaway test: a mocked Accred returning
`{"authorizations": []}` yields `[]` from `get_roles_by_user_id` with no raise.

So the exposure is bounded by the refresh-token lifetime, exactly as the
maintainer stated, and the PR body's "keeps their access until someone reads
the ERROR log" is an overstatement of the risk — see N4.

### One caveat the PR does not mention

Change 5 (login stamps `last_roles_sync_at`) makes a _login-time_ empty
stickier. Before this PR, a transient empty at login was self-correcting
within seconds: the wipe left the timestamp stale, so the next
`POST /v1/session` re-synced immediately and a healthy Accred response
restored the roles. Now the stamp is fresh, the TTL gate holds for 15 minutes,
and the guard cannot help (it needs `old_roles` non-empty, which the login
wipe just cleared).

Recovery latency for that case goes from ~seconds to ≤15 minutes. This is a
reasonable trade against the doubled provider load change 5 removes, but it is
a real interaction between changes 1 and 5 and should be stated in the plan.

---

## R1 (required) — the wholesale-drop raise can block login for real users

`_raise_on_wholesale_drop` fires whenever Accred returns ≥1 authorization and
none map. Because `get_user_by_user_id` calls `get_roles_by_user_id`
(`role_provider.py:499`) and `auth.py:412-420` converts `RoleProviderNetworkError`
into `503 "Auth service unavailable. Please check your VPN."`, that is a **hard
login failure**, not a degraded login.

Verified with throwaway tests against the real mapping loop. Both raise:

| Payload (single authorization)                                            | Before this PR          | After                         |
| ------------------------------------------------------------------------- | ----------------------- | ----------------------------- |
| `name: "calco2.user.newrole"` (valid namespace, not yet in `RoleName`)    | logs in with zero roles | **503 at login, permanently** |
| `name: "calco2.user.standard"`, `reason.resource: {}` (no `cf`/`altname`) | logs in with zero roles | **503 at login, permanently** |

The second row is the problem. The `searchauthorization=calco2.` filter means
Accred only ever returns `calco2.*` rows, so _any_ of the four drop conditions
firing on a single-authorization user produces the raise. Most people hold one
authorization on one unit — the issue's own hypothesis C says so — and the
maintainer's stated suspicion in #2531 is that **some authorizations lack a
cf/unit id today**. Shipping this converts those users' symptom from "403 on
protected pages" to "cannot log in at all, told to check their VPN". That is a
worse failure, not a louder one.

It also amplifies maintainer point 2 (no backoff): `SKIPPED_PROVIDER_UNAVAILABLE`
never stamps `last_roles_sync_at`, so each affected user re-hits Accred on
every `POST /v1/session`, forever, with no TTL throttle. A transient
fleet-wide cause is one thing; a permanent per-user data condition that polls
Accred unthrottled indefinitely is another.

### Does the raise buy anything the guard doesn't?

| Situation                      | With the raise                                      | With log-only                                   |
| ------------------------------ | --------------------------------------------------- | ----------------------------------------------- |
| Sync, user has stored roles    | `SKIPPED_PROVIDER_UNAVAILABLE` — no write, no stamp | `SKIPPED_SUSPICIOUS_EMPTY` — no write, no stamp |
| Sync, user has no stored roles | no write, no stamp                                  | `NO_CHANGE`, stamps the TTL                     |
| Login                          | **503**                                             | logs in with zero roles (pre-PR behaviour)      |

The wipe guard already covers the case the raise was written for. The raise's
only _distinct_ effects are the login 503 and skipping a TTL stamp for a
role-less user.

**Recommended fix:** keep `_raise_on_wholesale_drop`'s ERROR log verbatim —
naming the moved field from one log line is change 3's real value and it is
well done — and drop the `raise`. If the harder failure is wanted on the sync
path specifically, gate it there (the sync already has a safe abort), never on
the login critical path.

**Do not** apply the narrowing the PR body proposes in its own Question 3
("every authorization had a recognized name but was dropped later"). It
isolates the unknown-role case only; the missing-`cf` user has a recognized
name and is dropped later, so they would still get the 503. It fixes the less
likely half of the problem.

### R1b — the diagnostic misses the most likely schema move

The helper reads its payload defensively — `(first.get("reason") or {}).get("resource") or {}`
— but the loop it diagnoses does not: `role_provider.py:627` is
`auth.get("reason").get("resource")`. If the field that moves is `reason` or
`resource` itself (the exact class of change the helper exists to name), the
loop raises `AttributeError` on the first row and the helper never runs. The
error surfaces as the generic "Unexpected error fetching roles" with no field
names in it.

Confirmed with a throwaway test: an authorization with no `reason` key raises
`AttributeError`, not `RoleProviderNetworkError`.

One-line fix, same style as the helper:

```python
resource = (auth.get("reason") or {}).get("resource") or {}
```

---

## R2 (required) — the guard does not close every path

Maintainer question 1 asks whether the hole is closed in _every_ path. It is
not. Three writers can set a user's roles; the PR guards one.

| Writer                                                           | Guarded?                                              |
| ---------------------------------------------------------------- | ----------------------------------------------------- |
| `RoleSyncService.sync_user_roles`                                | yes — and correctly `force`-independent, see below    |
| `UserService._upsert_user_identity` → `user_repo.update` (login) | no, **by design** — login is the revocation authority |
| `UserRepository.bulk_upsert` (unit-sync ingestion)               | **no, and not by design**                             |

`user_repo.py:140-155` matches incoming users to existing rows by
`institutional_id` and calls `session.merge(user)` with a whole `User` object.
`merge` copies every attribute, so `roles_raw` on the persistent row is
overwritten by whatever the transient object carries.

The transient object comes from `AccredRoleProvider.map_api_user`
(`role_provider.py:539-552`), fed by `unit_sync_tasks.py:179` with each unit's
`responsible` dict (`unit_provider.py:143-156`) — which has `id`, `email`,
`display` and **no `roles` key**.

Verified empirically against the test DB: seed a user with roles, run
`UserService.bulk_upsert([map_api_user(responsible)])`, and the row comes back
with `roles_raw = None` and `last_roles_sync_at = None`. The roles are gone.

Two separate defects here:

1. **`map_api_user`'s `roles=` kwarg is silently discarded.** `roles` is a
   `@property` on `UserBase` backed by `roles_raw` (`models/user.py:331-349`);
   SQLModel's constructor does not invoke property setters, so
   `User(..., roles=[...])` leaves `roles_raw` at `None`. The mapper has never
   set roles at all. (`RoleProvider.map_api_user`'s `User(provider=..., **user_raw)`
   base implementation has the same problem.)
2. **`bulk_upsert` merges fields it was never asked to update.** It also resets
   `last_roles_sync_at` (and any other field absent from the source dict) to
   the model default.

This is not introduced by this PR, but it is squarely inside the invariant the
PR claims to establish, and it is a _better_ fit for the reported symptom than
hypotheses A/B/C: it hits only unit responsibles (explains "only some users"),
login rewrites the roles (explains "logging out and back in fixed it"), and it
recurs on the next dispatched unit sync (explains the recurrence). I have not
confirmed it caused the production incident — but it should be checked against
the timing of `POST /v1/sync/dispatch` runs before #2531 is called closed.

Smallest fix: have `bulk_upsert` update only the identity fields it actually
sources, rather than merging a whole `User`. Either way it needs a regression
test — this is exactly the shape of the bug the PR is about.

---

## `force=True` (maintainer question 1)

Correct. The guard at `role_sync_service.py:158` is
`if not new_roles and old_roles:` with no `force` term, so a forced sync cannot
wipe either. This matches the maintainer's decision to skip the hatch, and the
only production caller (`auth.py:666-667`) passes `force=False` anyway.

**Gap:** nothing pins it. The property the maintainer explicitly ruled on has
no test, so a future one-line edit reintroducing `and not force` would go
green. Add the assertion — it is three lines on top of an existing fixture:

```python
result = await service.sync_user_roles(user.id, _provider_returning([]), force=True)
assert result.outcome is RoleSyncOutcome.SKIPPED_SUSPICIOUS_EMPTY
```

---

## Tests (maintainer question 4)

`85 passed` across `test_role_sync_service.py`, `test_role_sync_skip.py`,
`test_role_provider.py`, `test_user_service.py`.

Two "fails without the fix" claims spot-checked by reverting the production
code, not by reading:

| Reverted                                    | Result                                                                                                                                                          |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| the wipe guard (`role_sync_service.py:158`) | `test_empty_provider_response_does_not_wipe_existing_roles` **FAILED**, `test_suspicious_empty_leaves_sync_timestamp_untouched` **FAILED** — 2 failed, 8 passed |
| the login stamp (`user_service.py:123`)     | `test_login_stamps_sync_time_so_next_session_call_is_ttl_gated` **FAILED** (`last_roles_sync_at is None`)                                                       |

Both claims hold. The test bodies also assert the right things — the
empty-response test checks `roles_changed is False` explicitly, with a comment
naming _why_ (it gates `sync_user_units`, which drops every association for a
unit-less role set). That is the non-obvious second-order consequence and it
is good that it is pinned.

The two deliberately-passing-both-ways tests are correctly labelled as such,
and `test_user_with_no_roles_receiving_no_roles_is_not_an_error` is the right
counterweight — without it the guard could plausibly have been written to make
role-less users re-poll forever.

Change 6's claim is also true: `login_test`'s old default `"co2.user.std"` is
not a `RoleName` value, so `TestRoleProvider.get_roles` hit its
`except ValueError: return []` (`role_provider.py:335-338`) and the debug login
produced a user with zero roles. Real bug, correctly fixed. Dev-only route.

Not covered, in rough priority order: `force=True` + empty (above);
`trigger_role_sync_for_user` never calling `sync_user_units` on a skip (only
the service-level `roles_changed is False` is asserted); the `bulk_upsert` path
in R2.

---

## Invariants

| Rule                                     | Verdict                                                                                                                                                                                                                                     |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No silent fallbacks                      | Improved substantially — this is the PR's whole point. R1b is the one remaining silent path (the loop's `AttributeError` swallows the diagnosis).                                                                                           |
| Authorization fails closed               | Held on the sync path. R1 fails _too_ closed on the login path — a hard 503 for a user whose data is merely unmapped.                                                                                                                       |
| No `# type: ignore` / `@ts-expect-error` | None added. Clean.                                                                                                                                                                                                                          |
| Functions ≤40 lines, ≤2 nesting          | **Violated.** `sync_user_roles` is 125 lines (`:92-216`), up ~25 from `dev`. Pre-existing, made worse. The four early-return blocks are each a natural extraction; not blocking, but it is drifting further from the rule with each change. |
| Commit in the route, not the service     | `sync_user_roles` commits at `:185`/`:197`. Pre-existing and defensible for a background task with no route, but worth an explicit `ponytail:`-style note so it does not read as an oversight.                                              |
| Backend is source of truth               | Held.                                                                                                                                                                                                                                       |

---

## Nits

- **N1** — `_role_sort_key(role) -> tuple` (`role_sync_service.py:46`) has an
  unannotated parameter and a bare `tuple` return. `ty` passes, but every
  other helper in the file is annotated. `role: Role` / `-> tuple[str, str, str | None]`.
- **N2** — a schema break now logs as `"Role sync aborted - provider unavailable"`
  in the service, because `_raise_on_wholesale_drop` reuses
  `RoleProviderNetworkError`. The provider's own ERROR line has the real
  diagnosis, but the service line above it in the log says the wrong thing. A
  distinct exception type (or an outcome that says "contract break") would
  read straight.
- **N3** — the TTL comparison at `:121` assumes `last_roles_sync_at` is
  timezone-aware. It is under Postgres; SQLite hands back naive values, which
  is why the new tests carry `.replace(tzinfo=UTC)`. Surfaced during the revert
  spot-check as a `TypeError`. Pre-existing, harmless in production, but the
  test comment is the only place it is written down.
- **N4** — two maintainer requests are still un-actioned on this branch. The
  PR body's Question 1 and the plan (`2531-...md:97-105`) both still say a
  revoked user "keeps their access until someone reads the ERROR log", which
  the maintainer asked to reword, and both still describe the one-line `force`
  hatch that was explicitly rejected. Follow-up issue #2539 _is_ open, so that
  request is done. Fix the wording in the same PR — the plan is the artefact
  the next person greps.
- **N5** — plan frontmatter is `status: in-progress`; flip to `delivered` when
  this merges, per the plan conventions.

---

## Checks run

```
uv run pytest tests/unit/services/test_role_sync_service.py \
  tests/unit/tasks/test_role_sync_skip.py \
  tests/unit/providers/test_role_provider.py \
  tests/unit/services/test_user_service.py -q
→ 85 passed

make lint        → ✅ backend ruff, frontend eslint+stylelint, docs, helm
make type-check  → ✅ ty (backend) + vue-tsc (frontend)
```

Frontend checks needed `npm ci` + `npx quasar prepare` in this worktree; the
diff is backend + docs only.
