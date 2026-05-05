---
status: delivered
last_updated: 2026-05-05
summary: Frontend architecture and persona flows.
---

# Frontend Overview

A Vue 3 + Quasar Single Page Application served from `frontend/`. This page is
the landing point: jump to the detail page that matches your task.

- [Component tree](01-overview/components.md) — pages, layouts, atomic design
  primitives, stores, routing.
- [Persona flows](01-overview/personas.md) — state diagrams for the data-entry
  user and the back-office user.
- [Design tokens](02-design-tokens.md) — SCSS tokens and theming.

## Quick Start

```bash
cd frontend
npm install
cp .env.example .env       # set VITE_API_BASE_URL
npm run dev                # http://localhost:9000
npm run build              # output in dist/spa/
```

`VITE_` is the only prefix Vite exposes to the client. Quasar config lives in
`quasar.config.js` (build targets, plugins, dev-server proxy).

## Project Layout

```text
frontend/src/
  api/         ky http client + endpoint constants
  boot/        Quasar boot files (i18n, plugins)
  components/  atoms / molecules / organisms / audit / charts / layout
  layouts/     MainLayout.vue
  pages/       app/, back-office/, system/  (one route = one page)
  router/      routes.ts, guards/
  stores/      Pinia stores (auth, modules, workspace, factors, …)
  i18n/        en, fr locale files
  css/         tokens and Quasar theme overrides
```

## Testing

Playwright covers both component and end-to-end suites; there is no Vitest
unit suite. Storybook interaction tests catch visual regressions.

```bash
npm run test-ct            # Playwright component tests
npm run test:e2e           # Playwright integration tests
npm run storybook:test     # Storybook test-runner
npm run lint               # ESLint
```

CI runs `test-ct` and `test:e2e` (see `.github/workflows/test.yml`). The
Storybook test-runner is not yet wired into CI; run `npm run storybook:test`
locally to exercise it.

## Authentication & Authorization

`LoginPage` redirects to `API_LOGIN_URL` (Microsoft Entra ID via backend);
`auth/me` populates the `auth` Pinia store with `roles_raw` and
`permissions`. Guards in `router/guards/` enforce access:
`requirePermission`, `requireModuleEditPermission`, `validateUnitGuard`,
`redirectToWorkspaceIfSelectedGuard`. See
[Auth Flow Across Layers](../architecture/04-auth-flow.md) for the full path.

## Further Reading

- [Component Breakdown](../architecture/09-component-breakdown.md)
- [ADR-002 Frontend Framework](../architecture-decision-records/002-frontend-framework.md)
- [Deployment Topology](../architecture/11-deployment-topology.md) — Nginx +
  Docker production setup (centralized there).
