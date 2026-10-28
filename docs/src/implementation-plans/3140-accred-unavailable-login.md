---
status: delivered
issue: 3140
last_updated: 2026-10-27
summary:
  "Accred 5xx, 401/403/429 and timeouts become RoleProviderNetworkError: the
  login callback redirects to a login page that says Accred is down, a
  new accred.request.failures counter feeds a critical AccredUnavailable
  alert, and role sync records the outage instead of swallowing it."
---

# 3140 — Make an Accred outage visible to users and ops

## The gap

2026-10-27: `api.epfl.ch/v1/persons/{id}` answered 500. Every login died
as a raw-JSON 401 "Authentication failed" and no alert fired.

`AccredRoleProvider` mapped only `httpx.ConnectError` to
`RoleProviderNetworkError`. A 5xx (`HTTPStatusError`) or a timeout
(a `RequestError`, not a `ConnectError`) escaped raw:

- `oauth_callback` sent it to its generic `except Exception`, a 401.
  Even the mapped case returned a JSON 503 saying "check your VPN".
- `RoleSyncService.sync_user_roles` catches only
  `RoleProviderNetworkError`, so the 500 reached `role_sync_tasks.py`,
  which logged "Role sync failed" and swallowed it.
  `role_sync.skipped{outcome=skipped_provider_unavailable}` never moved
  and `RoleSyncProviderUnavailable` (#2623) never fired.

## What shipped

### Provider (`app/providers/role_provider.py`)

Both `get_user_by_user_id` and `get_roles_by_user_id` route every
`httpx.HTTPError` through one helper, `_raise_accred_error`, which logs it
once and raises `RoleProviderNetworkError` on an outage: a 5xx, a 401/403
(our service credential is rejected), a 429 (rate-limited) or any
`httpx.RequestError`. It counts each outage first:

```python
_accred_request_failures = get_meter(__name__).create_counter(
    "accred.request.failures", unit="{failure}", ...
)
```

Attributes `endpoint` (`persons` / `authorizations`) and `status_code`
(the HTTP status, or the httpx exception class name such as
`ReadTimeout`). Never the user id. Exported as
`accred_request_failures_total`. Any other 4xx still raises
`HTTPStatusError` and is not counted: a 404 is an answer about this user,
not an outage. `_require_credentials` (missing Accred settings) counts
`endpoint=config, status_code=unconfigured` before it raises, so a
misconfigured pod alerts too.

Consequence for role sync: every outage above (5xx, 401/403/429,
timeout, connection error) now lands on
`SKIPPED_PROVIDER_UNAVAILABLE` (roles kept, `last_roles_sync_at` stamped,
one `ROLE_SYNC_TTL_MINUTES` backoff, counted). The admin
`POST /v1/users/{id}/revoke-roles` answers 200 with that outcome instead
of a 500.

### Callback (`app/api/v1/auth.py`)

`RoleProviderNetworkError` redirects (302) to
`{FRONTEND_URL}/login?reason=accred-unavailable`, with no language: the
backend cannot know it. The frontend `login-redirect` route forwards to
`/<lang>/login`, keeping the query, with the language from
`resolveLanguage` (locale cookie, then browser). The ERROR log and
the `login_failed` audit event (`reason: provider_unavailable`) are
kept. The other 401 paths and the state-mismatch redirect are unchanged.

### Frontend

`src/utils/loginReason.ts` maps `accred-unavailable` to
`login_accred_unavailable_message` (shape of `utils/unauthorized.ts`).
`LoginPage` passes `?reason=` to `LoginCard`, which renders the
`ErrorUnauthorized` highlight with `role="alert"`. Unknown or absent
reasons show nothing; the lookup uses `Object.hasOwn`, so inherited keys
such as `?reason=toString` are unknown too.

### Alert (`openshift-app-config`, all three envs)

`AccredUnavailable`, `severity: critical`, in the Auth group, same
sparse-counter two-arm pattern as `RoleSyncProviderUnavailable`, no
`absent()`. It co-fires with `RoleSyncProviderUnavailable`, which clears
after the backoff. Runbook row in
[04-operations](../infra/04-operations.md#ours-symptom-cause-action).

## Not in scope

- No dashboard panel, same as #2623.
