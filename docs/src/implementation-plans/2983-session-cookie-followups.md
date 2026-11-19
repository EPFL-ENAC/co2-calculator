---
status: delivered
issue: 2983
last_updated: 2026-11-10
summary: "Only GET /session renews the session cookie, re-asked hourly by the router guard; a failed session check shows a retry notice instead of the login page; logout waits for a check in flight. Fixes findings 2, 3, 6 of #2983 and folds in 5, 7, 8."
---

# Session cookie follow-ups from the #2982 review

Fixes findings #2, #6 and #3 of #2983 and folds in #5, #7 and #8, which
sit on the same lines. Amends [ADR-020](../architecture-decision-records/020-single-sliding-session-cookie.md)
and supersedes the renewal side effects of
[plan 2943](2943-single-session-cookie.md).

## What was wrong

- **#2 (P1).** A 503 or a network error on `GET /session` at bootstrap
  sent a signed-in user to `/login` until a full reload: the store marked
  the session as checked even when the check threw, and the guard read
  "no user" as "logged out".
- **#6.** Every request past half-life renewed the cookie, so a tab firing
  N parallel calls wrote N "Session renewed" audit rows and queued N role
  syncs (N Accred calls).
- **#3.** A renewal whose response landed after `DELETE /session` re-set
  the cookie, and the user stayed signed in after logout.

## Decision (maintainer, 2026-11-10)

Only `GET /session` renews. The router guard asks it again when its last
check is over an hour old (`SESSION_RECHECK_MS`, which must stay under
half the backend idle window, 24 h today).

## What shipped

Backend (`app/core/security.py`, `app/api/v1/auth.py`):

- `get_session_claims` decodes the cookie as a dependency of its own;
  FastAPI caches it per request, so `get_optional_user` and `GET /session`
  share one decode.
- `get_optional_user` resolves the user and no longer renews.
- `renew_session_if_due(claims, user, request, response, background_tasks)`
  runs last in `GET /session`. A route that raises before that line sends
  no cookie and queues no audit row (#7): FastAPI drops the injected
  response's headers and the background tasks on an exception.
- The renewed cookie takes `email`, `institutional_id` and `provider` from
  the user row, as login does, so a changed email reaches it (#8).
- A user without an `id` raises `ValueError` instead of auditing
  `user_id=0` (#5).
- `SessionRenewalMiddleware` is deleted: it existed so 304s, downloads and
  streams carried the renewed cookie, and those routes no longer renew.

Frontend (`stores/auth.ts`, `router/guards/authGuard.ts`, `App.vue`):

- `hasChecked` became `checkedAt` + `sessionCheckDue()`. A failed check
  leaves `checkedAt` alone, so the next navigation retries.
- `sessionUnavailable` is set when a check fails and no user is known. The
  guard then cancels the navigation and `App.vue` shows
  `SessionUnavailableNotice`; its button reloads the page. A failed hourly
  re-check keeps the user already known.
- `logout()` waits for a session check still in flight before the DELETE.

## Not folded

- **#9** (`frontend/.env.example`): no line touched here.
- Out of scope: #1, #4, #10, S1, S2. They stay open on #2983.

## Known limits

- A tab that stays on one route with no navigation or reload for a whole
  half-life (24 h) is not renewed and meets the session-expired redirect
  at `exp`. Before, any save renewed it.
- Another tab's `GET /session` crossing a logout can still re-set the
  cookie. Stateless sessions cannot close that; it is S1 (parked).

## Tests

Backend, `tests/integration/v1/test_auth_security.py`:

- `test_session_past_half_life_is_renewed_on_get_session`: one cookie, one
  audit row, one role sync, and the new cookie works.
- `test_renewed_claims_come_from_the_user_not_the_old_cookie` (#8).
- `test_other_routes_never_renew` (#6).
- `test_a_call_answered_after_logout_does_not_sign_back_in` (#3).
- `test_failed_get_session_carries_no_cookie_and_no_audit` (#7).
- `test_renewal_refuses_a_user_without_id` (#5).

Frontend, `tests/unit/session-guard.spec.ts` (Playwright CT): a 503 and a
network error are not a logout and the next navigation retries, the guard
re-checks after an hour and keeps the user when that fails, logout sends
its DELETE only after the check in flight answers, and the notice renders.
