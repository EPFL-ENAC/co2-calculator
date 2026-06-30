# Frontend Observability — Shared Packages Design

Status: design
Date: 2026-06-30
Scope: new external monorepo (`frontend-observability`), not co2-calculator itself

## Problem

co2-calculator's frontend carries a hand-rolled, Sentry/GlitchTip-compatible
error reporter (`frontend/src/utils/glitchtip.ts`) and a Quasar boot plugin that
wires it into the app (`frontend/src/boot/sentry.ts`). Other repos in the team
want the same crash visibility. Today the only way to share it is copy-paste,
which drifts.

The core reporter is already framework-agnostic (pure TS, zero deps — only
`fetch`/`crypto`/`localStorage`). The boot plugin is the coupled part: it
depends on Quasar (`boot`, `Notify`), on this app (`runtimeConfig`, i18n keys,
`ky`'s `HTTPError`), and on the reporter. Making the work reusable means
separating those concerns into published packages.

## Goals

- Publish reusable packages so any team frontend gets crash reporting by adding
  a dependency, not by copying files.
- Keep the framework-agnostic core usable by Vue, React, or vanilla consumers.
- Let consuming apps customize toast/UX behavior by passing arguments, not by
  re-implementing handlers.
- Preserve co2-calculator's current behavior after migration.

## Non-Goals

- Performance monitoring / tracing spans (the core deliberately emits IDs only;
  unchanged here).
- Vue and React adapters — not built now (YAGNI). The Quasar adapter is
  structured so a future adapter is a thin wrapper.
- A backend/distributed-tracing half.

## Decisions

| Decision            | Choice                                                             |
| ------------------- | ------------------------------------------------------------------ |
| Distribution        | Private npm registry (GitHub Packages)                             |
| Framework targets   | Pure-TS core + framework adapters (Vue/React/vanilla all possible) |
| Repo layout         | One monorepo, multiple published packages                          |
| Adapter UX scope    | Layered: wiring is minimal; default UX is an opt-in third layer    |
| Default UX location | Second tree-shakeable export inside the Quasar package             |
| npm scope           | `@epfl-enac`                                                       |
| Repo name           | `frontend-observability`                                           |

## Architecture

Three layers, each independently usable:

```
Layer 1  @epfl-enac/observability-core      reporter: captureError, breadcrumbs, trace
Layer 2  @epfl-enac/observability-quasar     wiring: handlers -> captureError, exposes hooks
Layer 3  createQuasarNotifyUx (same package) toasts + reload prompt, parameterized
```

Repo structure:

```
frontend-observability/
├── packages/
│   ├── core/      → @epfl-enac/observability-core
│   └── quasar/    → @epfl-enac/observability-quasar
├── pnpm-workspace.yaml
├── .changeset/
└── .github/workflows/
```

### Package 1: `@epfl-enac/observability-core`

`glitchtip.ts` lifted out essentially unchanged.

- Public API (unchanged): `initGlitchTip`, `captureError`, `addBreadcrumb`,
  `startNavigationTrace`, and the `GlitchTipOptions` / `CaptureContext` types.
- **Addition:** move `isChunkLoadError(err)` out of co2-calculator's
  `boot/sentry.ts` into core and export it. It is pure and framework-agnostic;
  every consumer wants it, and no consumer should re-type the regexes.
- Ships ESM + `.d.ts` only (browser target, no CJS).
- Hard invariant: zero runtime dependencies.

### Package 2: `@epfl-enac/observability-quasar`

Two tree-shakeable entry points.

**Entry A — wiring (minimal).** A boot-plugin factory that:

- calls `initGlitchTip` with the passed config,
- wires Vue `errorHandler`, `router.onError`, `router.afterEach`
  (breadcrumb + `startNavigationTrace`), and `window` `error` /
  `unhandledrejection` → `captureError`,
- exposes an optional `ux` hook object; it has no knowledge of toasts, i18n, or
  `ky`.

The framework-generic handler-wiring is itself a separately-exported function so
a future `-vue` / `-react` adapter is a thin wrapper, not a rewrite.

Hook interface:

```ts
interface ObservabilityUx {
  onError?(err: unknown, ctx: ErrorContext): void; // e.g. toast
  onChunkLoadError?(err: unknown): void; // e.g. reload prompt
}
```

Dependencies: `quasar` (peer) + `@epfl-enac/observability-core`. No `ky`, no
`runtimeConfig`, no i18n keys, no `Notify` in this layer.

**Entry B — default UX (opt-in).** `createQuasarNotifyUx(...)` returns a
ready-made `ObservabilityUx` reproducing co2-calculator's current behavior:
Quasar `Notify` toasts on error + the chunk-load "new version, reload?" prompt.
It is parameterized, not hardcoded:

```ts
createQuasarNotifyUx({
  t, // i18n translate fn — no hardcoded strings
  isHandled: (e) => e instanceof HTTPError, // suppress double-toast (the ky case)
  notifyOptions: { position: "top", timeout: 5000 }, // styling overrides
});
```

Apps that omit `ux` get pure wiring and don't bundle the UX (tree-shaken). Apps
that want a different look override `notifyOptions` or supply their own
`ObservabilityUx`.

## Tooling

Aligned to the team's existing stack (npm + Vite/Rollup); no unfamiliar tools.

- **Package manager:** npm workspaces (native, npm 7+).
- **Build:** Vite library mode (Rollup under the hood — same as the app). Each
  package has a small `vite.config` emitting ESM, with `vite-plugin-dts` for the
  `.d.ts` files.
- **Type-check & declarations:** `tsc` / `vite-plugin-dts` (the proven path —
  the published `.d.ts` is the package contract). `tsgo` (TypeScript's native Go
  port, "TS 7") may be added later as a _fast CI/local typecheck only_, once it
  is confirmed to emit identical declarations; it is preview as of 2026 and not
  the sole build path.
- **Versioning & publish:** no Changesets. Bump per package with `npm version`,
  push a git tag; a GitHub Actions workflow runs `npm publish` to GitHub
  Packages under `@epfl-enac` on that tag.
- **CI:** GitHub Actions — lint / typecheck / build / test on PR; publish on tag.

## Testing

The core is pure TS, so it gets real **vitest** unit tests in the library repo
(vitest is vite-native, so it reuses the build's `vite.config`; co2-calculator's
no-vitest constraint is a harness limitation of that app, not of a standalone
library). Coverage:

- DSN parsing (valid, malformed → disabled + console.error)
- envelope shape (3 newline-delimited JSON lines, headers present)
- `toError` (Error, string, message-bearing object, true non-Error → `NonError`)
- `parseStack` (Chrome and Firefox/Safari frame formats)
- consecutive-dedupe (`lastSig`)
- `ignoreErrors` matching (string + RegExp)
- `isChunkLoadError` (each engine's message variant)

The Quasar adapter gets lighter smoke tests over handler wiring and the default
UX factory.

## Migration of co2-calculator (follow-up, after packages publish)

1. Replace `frontend/src/utils/glitchtip.ts` with
   `@epfl-enac/observability-core`.
2. Rewrite `frontend/src/boot/sentry.ts` against
   `@epfl-enac/observability-quasar`: build config from `runtimeConfig`, call the
   boot factory, and pass `createQuasarNotifyUx({ t, isHandled: e => e instanceof
HTTPError, ... })` to reproduce today's toasts, reload prompt, and HTTPError
   double-toast suppression.
3. `isChunkLoadError` now comes from core; delete the local copy.

Net effect: `boot/sentry.ts` shrinks to config + UX wiring; all reusable logic
moves to the packages. App keeps its UX; the wiring is shared.

## Open questions

None outstanding. npm scope, repo name, layering, and UX location are decided
above.
