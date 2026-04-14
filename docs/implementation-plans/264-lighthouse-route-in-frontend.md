# Lighthouse CI: Frontend Route Coverage

Lighthouse CI previously only audited the login page because all
protected routes redirect unauthenticated users. This document
describes how the bypass works, what is audited in CI vs locally,
and what cannot be fully tested.

## Problem

The app requires authentication to access any page beyond `/en/login`.
Lighthouse CI runs against a static build with no backend, so:

- `authGuard` calls `GET /auth/me` → fails → redirects to login
- `validateUnitGuard` calls `GET /units` → fails → redirects to
  workspace-setup
- `requirePermission` checks `auth.user.permissions` → null → redirects
  to `/unauthorized`

Result: every route audited as the login page.

## Solution: Runtime Bypass Flag

The CI workflow injects a script tag into the built `index.html`
**after** the build, before Lighthouse runs:

```js
window.__LIGHTHOUSE_BYPASS__ = true;
```

All navigation guards check this flag and return `true` immediately
when it is set. The flag is never baked into the production build —
it only exists in the local copy used by the Lighthouse static server.

### Guards extended

| Guard                         | File                                     |
| ----------------------------- | ---------------------------------------- |
| `authGuard`                   | `src/router/guards/authGuard.ts`         |
| `validateUnitGuard`           | `src/router/guards/validateUnitGuard.ts` |
| `requirePermission`           | `src/router/guards/permissionGuard.ts`   |
| `requireModuleEditPermission` | `src/router/guards/permissionGuard.ts`   |

Pages render their intended component structure but make no real API
calls (no backend). This is intentional: Lighthouse audits static
structure, not live data.

## Two Configs

Running Lighthouse on all routes in CI would take ~36 minutes. The
approach splits audit scope into two configs:

| Config                  | Used by           | Routes | Runs | Est. time |
| ----------------------- | ----------------- | ------ | ---- | --------- |
| `.lighthouserc.json`    | `make lighthouse` | 24     | 1    | ~12 min   |
| `.lighthouserc.ci.json` | CI workflow       | 5      | 1    | ~2 min    |

### CI routes (`.lighthouserc.ci.json`)

The 5 routes cover the main user journey:

- `/en/login`
- `/en/login-test`
- `/en/workspace-setup`
- `/en/MOCK/2024/home`
- `/en/MOCK/2024/results`

`MOCK` and `2024` are placeholder values. With `validateUnitGuard`
bypassed, the workspace pages render their component shells.

### Local routes (`.lighthouserc.json`)

Run `make lighthouse` from the `frontend/` directory for a full
24-route audit covering all workspace, back-office, and system pages.

## Known Limitations

### Not all pages are audited in CI

Auditing all 24 routes would exceed acceptable CI time. The 5 CI
routes cover the critical user path. For full coverage, run locally.

### Green Web Foundation check fails on localhost

The ecoindex plugin includes a Green Web Foundation check. It always
fails on `localhost` because the foundation's API requires a public
domain. This is expected and does not indicate a problem.

> `The Green Web Foundation — Localhost can't be checked.`

This check passes when run against a deployed public URL.

### Pages render without data

Because no backend is running, all API calls fail silently. Pages
show empty states or loading spinners. Lighthouse still audits HTML
structure, accessibility, performance of static assets, and SEO
metadata — which is the goal.

## Running Locally

```bash
cd frontend
make lighthouse
```

This builds the SPA, injects the bypass flag, starts a local server
with SPA history-mode support (`serve -s`), and audits all 24 routes.
Reports are saved to `frontend/.lighthouseci/`.
