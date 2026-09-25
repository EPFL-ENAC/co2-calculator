# Role Synchronization Architecture

Roles are read from the database on every request; the role provider
(Accred, JWT claims, test) is consulted only in the background. Current
details, including the TTL gate, the empty-response guard and the admin
force path, live in the rendered docs:
[Auth Flow, section 6a](src/architecture/04-auth-flow.md#6a-background-role-sync).

## Trigger

A background role sync runs whenever the session cookie is renewed, which
happens on the first request past half the idle window (#2943). With the
deployed 48 h idle window that is at most once per 24 h of activity per
user. `GET /v1/session` itself never syncs: it returns cached DB roles.

The former `/me` and `/refresh` endpoints are gone: `/me` became
`GET /v1/session`, and the refresh endpoint was replaced by server-side
renewal.

## Consistency model

Eventual: a role granted or revoked upstream lands at the user's next
renewal, bounded by `ROLE_SYNC_TTL_MINUTES` debounce. An admin can force it
immediately with `POST /v1/users/{user_id}/revoke-roles`.

## Safety guarantees

1. **Authorization always uses DB roles** — no provider call on the request path.
2. **Failures don't block requests** — background sync errors are logged and counted.
3. **No sync storms** — the TTL gate debounces the parallel renewals of one page load.
4. **Unit cleanup** — removed roles clean up unit associations.
