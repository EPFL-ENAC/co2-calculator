---
status: delivered
issue: 2308
last_updated: 2026-08-26
title: "Logout button on the 403 page"
summary: "Always show a Logout button on /unauthorized: a broken session (e.g. a stale account after the 1.4.1 DB reset) 403s every call, the global 403 hook redirects here without a reason, and the page previously offered only a Home button that looped straight back."
---

## Problem

Since release 1.4.1 (DB dropped), a user whose account/session no longer
matches the database gets a 403 on every API call. The global hook in
`frontend/src/api/http.ts` redirects any 403 to `/unauthorized` — with no
`reason` query param in this case. The page only showed the Logout button for
the known dead-end reasons (`no-unit`, `no-open-year`); a bare 403 showed
"Home" instead, which re-triggers the 403 and bounces right back. The page is
fullscreen (no header), so there was no way to log out at all.

## Fix

`frontend/src/pages/ErrorUnauthorized.vue`:

- The Logout button is now always rendered. It stays the primary (filled)
  button on dead-end reasons and becomes outline next to Home / back-office.
- Home keeps its previous behaviour but inverted guard: hidden only for the
  dead-end reasons where it would loop.
- Back-office button unchanged.

No backend change: `DELETE /session` (`backend/app/api/v1/auth.py`) has no
permission dependency — it only clears the auth/refresh cookies — so logout
succeeds even when every other call 403s.

## Testing

`eslint` and `vue-tsc` pass. Existing pure-logic specs in
`tests/unit/no-workspace-landing.spec.ts` don't pin button visibility and are
unaffected.
