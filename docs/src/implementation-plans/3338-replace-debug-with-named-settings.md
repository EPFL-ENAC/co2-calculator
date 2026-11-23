---
status: delivered
issue: 3338
last_updated: 2026-11-20
summary: Replace the DEBUG setting with settings that say what they do. The test login and the stack traces in responses get their own settings, false by default. The cookie flag and the Loki label use settings that already exist.
---

# Replace DEBUG with named settings

`DEBUG` switches on six unrelated things. The dev deployment needs only
one of them, the test login, but it also gets stack traces in its
responses. This plan gives each effect a setting with a name that says
what it does.

## The mapping

| Effect today                                            | Setting after the change                                  | Default |
| ------------------------------------------------------- | --------------------------------------------------------- | ------- |
| `/auth/login-test` exists                               | `TEST_LOGIN_ROUTE_ENABLED`                                | false   |
| A failed OAuth login returns the stack trace in the 401 | `DEBUG_STACK_TRACE_ENABLED`                               | false   |
| `FastAPI(debug=...)` returns a 500 with the stack trace | `DEBUG_STACK_TRACE_ENABLED`                               | false   |
| The OAuth session cookie drops its Secure flag          | `COOKIE_SECURE`, which exists                             | true    |
| The Loki `env` label falls back to `dev`                | If `LOKI_ENABLED` is true, boot requires `LOKI_LABEL_ENV` | none    |
| `python -m app.main` reloads with one worker            | removed, nothing runs `python -m app.main`                | none    |

`DEBUG` is deleted. An old `DEBUG=true` no longer does anything, because
the project keeps no backward-compatibility paths.

## Environments

| Environment                       | Change                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Stage, prod                       | None. Each new setting is false by default. Their old `DEBUG: "False"` lines become unused.               |
| Dev                               | The ops overlay sets `TEST_LOGIN_ROUTE_ENABLED: "true"` and `LOKI_LABEL_ENV: "dev"`, and removes `DEBUG`. |
| Compose, Skaffold, `.env.example` | `TEST_LOGIN_ROUTE_ENABLED` and `DEBUG_STACK_TRACE_ENABLED` are true.                                      |

> CAUTION: Merge the dev ops PR before this change reaches dev. If the
> backend deploys first, dev loses the test login.

## Tests

- If `TEST_LOGIN_ROUTE_ENABLED` is false, the test login route does not
  exist.
- A failed OAuth login has no stack trace in the response unless
  `DEBUG_STACK_TRACE_ENABLED` is true.
- The OAuth session cookie follows `COOKIE_SECURE`.
- If `LOKI_ENABLED` is true and `LOKI_LABEL_ENV` is empty, the app does not
  start.

## Subsequent step

The change ships in PR #3325, with the other security audit fixes.
Merge the dev ops PR first, then #3325.
