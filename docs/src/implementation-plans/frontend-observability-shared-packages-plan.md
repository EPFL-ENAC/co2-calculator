# Frontend Observability — Shared Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract co2-calculator's GlitchTip error reporter and Quasar boot wiring into a published `frontend-observability` monorepo so any team frontend gets crash reporting by adding a dependency.

**Architecture:** One git repo (`frontend-observability`) using npm workspaces, holding two publishable packages. `@epfl-enac/observability-core` is the framework-agnostic reporter (lifted from `glitchtip.ts`, zero deps). `@epfl-enac/observability-quasar` wires the reporter into a Quasar app and exposes optional UX hooks; its second entry point `/ux` ships a parameterized default toast+reload adapter.

**Tech Stack:** TypeScript, npm workspaces, Vite library mode (Rollup) + `vite-plugin-dts`, Vitest (jsdom), GitHub Actions, GitHub Packages registry.

## Global Constraints

- npm workspaces only — no pnpm, no yarn, no Changesets, no tsup.
- `@epfl-enac/observability-core` has **zero runtime dependencies** (hard invariant).
- All packages publish to GitHub Packages under the `@epfl-enac` scope.
- Packages ship **ESM + `.d.ts` only** (browser target, no CJS).
- Node 20+, npm 10+.
- Reproduce co2-calculator's current behavior exactly; no behavior changes during extraction.
- This plan builds the repo. Migrating co2-calculator to consume the packages is a **separate follow-up** (Task 11 documents it; it is not executed here).

---

### Task 1: Monorepo scaffold

**Files:**

- Create: `package.json` (root)
- Create: `.gitignore`
- Create: `.npmrc`
- Create: `tsconfig.base.json`
- Create: `README.md`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: a `frontend-observability` repo where `npm install` succeeds and `packages/*` are recognized workspaces.

- [ ] **Step 1: Create the new repo locally**

```bash
mkdir frontend-observability && cd frontend-observability
git init
```

- [ ] **Step 2: Write the root `package.json`**

```json
{
  "name": "frontend-observability",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "engines": { "node": ">=20", "npm": ">=10" },
  "workspaces": ["packages/*"],
  "scripts": {
    "build": "npm run build --workspaces --if-present",
    "test": "npm run test --workspaces --if-present",
    "typecheck": "npm run typecheck --workspaces --if-present",
    "lint": "eslint ."
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vite-plugin-dts": "^4.2.0",
    "vitest": "^2.1.0",
    "jsdom": "^25.0.0",
    "eslint": "^9.0.0"
  }
}
```

- [ ] **Step 3: Write `.gitignore`**

```
node_modules/
dist/
*.tsbuildinfo
.DS_Store
```

- [ ] **Step 4: Write `.npmrc`** (points the scope at GitHub Packages)

```
@epfl-enac:registry=https://npm.pkg.github.com
```

- [ ] **Step 5: Write `tsconfig.base.json`** (shared compiler options)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "declaration": true,
    "skipLibCheck": true,
    "verbatimModuleSyntax": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

- [ ] **Step 6: Write a minimal `README.md`**

```markdown
# frontend-observability

GlitchTip/Sentry-compatible frontend error reporting for EPFL-ENAC apps.

- `@epfl-enac/observability-core` — framework-agnostic reporter (zero deps)
- `@epfl-enac/observability-quasar` — Quasar boot wiring + optional default UX

See each package's README for usage.
```

- [ ] **Step 7: Install and verify**

Run: `npm install`
Expected: completes without error; `node_modules/` created. (No workspaces have packages yet — that's fine.)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold frontend-observability monorepo"
```

---

### Task 2: Core package — lift the reporter + characterization tests

**Files:**

- Create: `packages/core/package.json`
- Create: `packages/core/tsconfig.json`
- Create: `packages/core/src/glitchtip.ts`
- Create: `packages/core/src/index.ts`
- Test: `packages/core/test/reporter.test.ts`

**Interfaces:**

- Consumes: nothing from other packages.
- Produces (public API, re-exported from `src/index.ts`):
  - `initGlitchTip(opts: GlitchTipOptions): void`
  - `captureError(error: unknown, ctx?: CaptureContext): void`
  - `addBreadcrumb(message: string, category?: string): void`
  - `startNavigationTrace(): void`
  - types `GlitchTipOptions`, `CaptureContext`

> **Note on TDD here:** the reporter is _ported_ working code, so these are
> **characterization tests** — they lock current behavior. Write the source by
> copying the existing file, then write tests that pin its observable output.
> Genuinely new code (Task 3 onward) follows strict test-first TDD.

- [ ] **Step 1: Copy the reporter source**

Copy `co2-calculator/frontend/src/utils/glitchtip.ts` **verbatim** into
`packages/core/src/glitchtip.ts`. Do not change its contents in this task.

- [ ] **Step 2: Write `packages/core/src/index.ts`**

```ts
export {
  initGlitchTip,
  captureError,
  addBreadcrumb,
  startNavigationTrace,
} from "./glitchtip";
export type { GlitchTipOptions, CaptureContext } from "./glitchtip";
```

- [ ] **Step 3: Write `packages/core/package.json`**

```json
{
  "name": "@epfl-enac/observability-core",
  "version": "0.1.0",
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" }
  },
  "files": ["dist"],
  "publishConfig": { "registry": "https://npm.pkg.github.com" },
  "scripts": {
    "build": "vite build",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 4: Write `packages/core/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "include": ["src", "test"]
}
```

- [ ] **Step 5: Write the failing characterization tests**

`packages/core/test/reporter.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { captureError, initGlitchTip } from "../src/index";

const DSN = "https://pubkey@glitchtip.example.com/42";

// Parse a captured envelope body (3 newline-delimited JSON lines) into its event.
function eventFrom(body: string) {
  const [, , event] = body.split("\n");
  return JSON.parse(event);
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 200 })));
  vi.stubGlobal("fetch", fetchMock);
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("initGlitchTip", () => {
  it("disables reporting and logs on a malformed DSN", () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    initGlitchTip({ dsn: "not-a-dsn" });
    captureError(new Error("boom"));
    expect(err).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("captureError envelope", () => {
  it("POSTs a Sentry envelope with the error type and message", () => {
    initGlitchTip({ dsn: DSN, environment: "test", release: "1.2.3" });
    captureError(new TypeError("kaboom"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/42/envelope/?sentry_key=pubkey");
    const event = eventFrom(init.body as string);
    expect(event.exception.values[0].type).toBe("TypeError");
    expect(event.exception.values[0].value).toBe("kaboom");
    expect(event.release).toBe("1.2.3");
    expect(event.environment).toBe("test");
  });

  it("tags a non-Error rejection as a synthetic NonError", () => {
    initGlitchTip({ dsn: DSN });
    captureError({ code: "E_TEST" });
    const event = eventFrom(fetchMock.mock.calls[0][1].body as string);
    expect(event.exception.values[0].type).toBe("NonError");
    expect(event.exception.values[0].mechanism.synthetic).toBe(true);
  });

  it("drops messages matching ignoreErrors", () => {
    initGlitchTip({ dsn: DSN, ignoreErrors: ["ResizeObserver loop"] });
    captureError(new Error("ResizeObserver loop limit exceeded"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("dedupes an identical consecutive capture", () => {
    initGlitchTip({ dsn: DSN });
    const e = new Error("same");
    captureError(e);
    captureError(e);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 6: Run the tests to verify they pass against the ported code**

Run: `npm test -w @epfl-enac/observability-core`
Expected: PASS (5 tests). If any fail, the port diverged from the original — fix the port, not the test.

- [ ] **Step 7: Commit**

```bash
git add packages/core
git commit -m "feat(core): lift GlitchTip reporter with characterization tests"
```

---

### Task 3: Core package — relocate and export `isChunkLoadError`

**Files:**

- Modify: `packages/core/src/glitchtip.ts` (append the function)
- Modify: `packages/core/src/index.ts` (export it)
- Test: `packages/core/test/chunk-load.test.ts`

**Interfaces:**

- Consumes: nothing.
- Produces: `isChunkLoadError(err: unknown): boolean` from the package root.
  (Task 5's Quasar wiring imports this.)

> Strict TDD: this function currently lives in co2-calculator's
> `boot/sentry.ts`. We re-create it in core test-first so every consumer shares
> one definition.

- [ ] **Step 1: Write the failing test**

`packages/core/test/chunk-load.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isChunkLoadError } from "../src/index";

describe("isChunkLoadError", () => {
  it.each([
    "Failed to fetch dynamically imported module: https://x/y.js",
    "error loading dynamically imported module",
    "Importing a module script failed.",
    "Unable to preload CSS for /assets/x.css",
    "Loading chunk 42 failed",
  ])("matches %s", (message) => {
    expect(isChunkLoadError(new Error(message))).toBe(true);
  });

  it("ignores unrelated errors", () => {
    expect(isChunkLoadError(new Error("TypeError: x is undefined"))).toBe(
      false,
    );
  });

  it("handles non-Error input", () => {
    expect(isChunkLoadError("Loading chunk 7 failed")).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -w @epfl-enac/observability-core -- chunk-load`
Expected: FAIL with "isChunkLoadError is not exported".

- [ ] **Step 3: Add the function to `packages/core/src/glitchtip.ts`**

Append at the end of the file:

```ts
// A route's lazy chunk (or its CSS) failed to load — usually a stale client
// after a deploy requesting hashed chunks that no longer exist. Messages differ
// per engine, hence the broad match. Lifted here so every consumer shares one
// definition instead of re-typing the regexes.
export function isChunkLoadError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err);
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /Unable to preload CSS/i.test(message) ||
    /Loading chunk \S+ failed/i.test(message)
  );
}
```

- [ ] **Step 4: Export it from `packages/core/src/index.ts`**

```ts
export {
  initGlitchTip,
  captureError,
  addBreadcrumb,
  startNavigationTrace,
  isChunkLoadError,
} from "./glitchtip";
export type { GlitchTipOptions, CaptureContext } from "./glitchtip";
```

- [ ] **Step 5: Run to verify it passes**

Run: `npm test -w @epfl-enac/observability-core -- chunk-load`
Expected: PASS (7 cases).

- [ ] **Step 6: Commit**

```bash
git add packages/core
git commit -m "feat(core): relocate and export isChunkLoadError"
```

---

### Task 4: Core package — Vite library build

**Files:**

- Create: `packages/core/vite.config.ts`

**Interfaces:**

- Consumes: the core source.
- Produces: `packages/core/dist/index.js` (ESM) + `packages/core/dist/index.d.ts`.

- [ ] **Step 1: Write `packages/core/vite.config.ts`**

```ts
import { resolve } from "node:path";
import { defineConfig } from "vite";
import dts from "vite-plugin-dts";

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      formats: ["es"],
      fileName: "index",
    },
    rollupOptions: { external: [] }, // zero deps — bundle nothing external
  },
  plugins: [dts({ rollupTypes: true, include: ["src"] })],
  test: { environment: "jsdom" },
});
```

- [ ] **Step 2: Build and verify output**

Run: `npm run build -w @epfl-enac/observability-core`
Expected: PASS; `dist/index.js` and `dist/index.d.ts` exist.

- [ ] **Step 3: Verify the type contract exposes the public API**

Run: `grep -E "isChunkLoadError|initGlitchTip|captureError" packages/core/dist/index.d.ts`
Expected: all three names present.

- [ ] **Step 4: Commit**

```bash
git add packages/core/vite.config.ts
git commit -m "build(core): Vite library build with declaration emit"
```

---

### Task 5: Quasar package — UX interface + framework-generic wiring

**Files:**

- Create: `packages/quasar/package.json`
- Create: `packages/quasar/tsconfig.json`
- Create: `packages/quasar/src/wiring.ts`
- Test: `packages/quasar/test/wiring.test.ts`

**Interfaces:**

- Consumes (from `@epfl-enac/observability-core`): `captureError`, `addBreadcrumb`, `startNavigationTrace`, `isChunkLoadError`.
- Produces:
  - `interface ObservabilityUx { onError?(err, ctx): void; onChunkLoadError?(err): void }`
  - `interface ErrorContext { mechanism: string; info?: string }`
  - `wireVueErrorHandlers(opts: { app: App; router: Router; ux?: ObservabilityUx }): void`

- [ ] **Step 1: Write `packages/quasar/package.json`**

```json
{
  "name": "@epfl-enac/observability-quasar",
  "version": "0.1.0",
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" },
    "./ux": { "types": "./dist/ux.d.ts", "import": "./dist/ux.js" }
  },
  "files": ["dist"],
  "publishConfig": { "registry": "https://npm.pkg.github.com" },
  "dependencies": { "@epfl-enac/observability-core": "^0.1.0" },
  "peerDependencies": {
    "quasar": "^2.0.0",
    "vue": "^3.0.0",
    "vue-router": "^4.0.0"
  },
  "scripts": {
    "build": "vite build",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 2: Write `packages/quasar/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "include": ["src", "test"]
}
```

- [ ] **Step 3: Install so the workspace links core into quasar**

Run: `npm install`
Expected: `@epfl-enac/observability-core` resolves from the workspace.

- [ ] **Step 4: Write the failing test**

`packages/quasar/test/wiring.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const capture = vi.fn();
const breadcrumb = vi.fn();
const startTrace = vi.fn();
vi.mock("@epfl-enac/observability-core", () => ({
  captureError: (...a: unknown[]) => capture(...a),
  addBreadcrumb: (...a: unknown[]) => breadcrumb(...a),
  startNavigationTrace: () => startTrace(),
  isChunkLoadError: (e: unknown) =>
    e instanceof Error && e.message.includes("chunk"),
}));

import { wireVueErrorHandlers } from "../src/wiring";

function makeApp() {
  return { config: { errorHandler: undefined } } as never;
}
function makeRouter() {
  const handlers: {
    error?: (e: unknown) => void;
    after?: (t: never, f: never) => void;
  } = {};
  return {
    onError: (h: (e: unknown) => void) => (handlers.error = h),
    afterEach: (h: (t: never, f: never) => void) => (handlers.after = h),
    _fireError: (e: unknown) => handlers.error?.(e),
    _fireAfter: (t: never, f: never) => handlers.after?.(t, f),
  } as never as import("vue-router").Router & {
    _fireError(e: unknown): void;
    _fireAfter(t: unknown, f: unknown): void;
  };
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("wireVueErrorHandlers", () => {
  it("captures vue errors and calls ux.onError", () => {
    const app = makeApp();
    const router = makeRouter();
    const onError = vi.fn();
    wireVueErrorHandlers({ app, router, ux: { onError } });
    app.config.errorHandler!(new Error("render fail"), null, "render");
    expect(capture).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ mechanism: "vue" }),
    );
    expect(onError).toHaveBeenCalledWith(expect.any(Error), {
      mechanism: "vue",
      info: "render",
    });
  });

  it("calls onChunkLoadError only for chunk-load router errors", () => {
    const router = makeRouter();
    const onChunkLoadError = vi.fn();
    wireVueErrorHandlers({ app: makeApp(), router, ux: { onChunkLoadError } });
    router._fireError(new Error("plain nav error"));
    expect(onChunkLoadError).not.toHaveBeenCalled();
    router._fireError(new Error("Loading chunk 3 failed"));
    expect(onChunkLoadError).toHaveBeenCalledTimes(1);
  });

  it("starts a trace and records a breadcrumb after navigation", () => {
    const router = makeRouter();
    wireVueErrorHandlers({ app: makeApp(), router });
    router._fireAfter({ fullPath: "/b" }, { fullPath: "/a" });
    expect(startTrace).toHaveBeenCalledTimes(1);
    expect(breadcrumb).toHaveBeenCalledWith("/a → /b", "navigation");
  });
});
```

- [ ] **Step 5: Run to verify it fails**

Run: `npm test -w @epfl-enac/observability-quasar`
Expected: FAIL (`wiring.ts` does not exist).

- [ ] **Step 6: Write `packages/quasar/src/wiring.ts`**

```ts
import type { App, ComponentPublicInstance } from "vue";
import type { Router } from "vue-router";
import {
  addBreadcrumb,
  captureError,
  isChunkLoadError,
  startNavigationTrace,
} from "@epfl-enac/observability-core";

export interface ErrorContext {
  mechanism: string;
  info?: string;
}

// Optional UX layer. Wiring calls these; the app decides what they do (toast,
// reload prompt). No knowledge of toasts/i18n lives here.
export interface ObservabilityUx {
  onError?(err: unknown, ctx: ErrorContext): void;
  onChunkLoadError?(err: unknown): void;
}

export interface WireOptions {
  app: App;
  router: Router;
  ux?: ObservabilityUx;
}

// Shallow (depth-1) copy of props for the report; nested values collapse to
// "[Object]"/"[Array]" to avoid circular refs and giant payloads.
function shallowProps(
  props: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props ?? {})) {
    out[key] =
      value === null || typeof value !== "object"
        ? value
        : Array.isArray(value)
          ? "[Array]"
          : "[Object]";
  }
  return out;
}

function vueErrorContext(
  instance: ComponentPublicInstance | null,
  info: string,
): Record<string, unknown> {
  const type = instance?.$?.type as
    | { name?: string; __name?: string }
    | undefined;
  return {
    componentName: type?.name || type?.__name || "Anonymous Component",
    lifecycleHook: info,
    propsData: shallowProps(instance?.$props),
  };
}

function installWindowHandlers(ux?: ObservabilityUx): void {
  window.addEventListener("error", (event) => {
    if (event.message?.includes("ResizeObserver loop")) {
      event.stopImmediatePropagation();
      event.stopPropagation();
      event.preventDefault();
      return;
    }
    const err = event.error ?? event.message;
    captureError(err, { mechanism: "onerror" });
    ux?.onError?.(err, { mechanism: "onerror" });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    captureError(reason, { mechanism: "onunhandledrejection", handled: false });
    ux?.onError?.(reason, { mechanism: "onunhandledrejection" });
  });
}

// Wire a Vue app + router into the reporter. Framework-generic (no Quasar
// import) so a future plain-Vue adapter reuses this as-is.
export function wireVueErrorHandlers({ app, router, ux }: WireOptions): void {
  const previous = app.config.errorHandler;
  app.config.errorHandler = (err, instance, info) => {
    if (typeof previous === "function") previous(err, instance, info);
    captureError(err, {
      mechanism: "vue",
      contexts: { vue: vueErrorContext(instance, info) },
    });
    ux?.onError?.(err, { mechanism: "vue", info });
  };

  router.onError((err) => {
    captureError(err, { mechanism: "vue-router" });
    if (isChunkLoadError(err)) ux?.onChunkLoadError?.(err);
  });

  router.afterEach((to, from) => {
    startNavigationTrace();
    addBreadcrumb(`${from.fullPath} → ${to.fullPath}`, "navigation");
  });

  installWindowHandlers(ux);
}
```

- [ ] **Step 7: Run to verify it passes**

Run: `npm test -w @epfl-enac/observability-quasar`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add packages/quasar
git commit -m "feat(quasar): framework-generic Vue error wiring with UX hooks"
```

---

### Task 6: Quasar package — boot-plugin factory

**Files:**

- Create: `packages/quasar/src/index.ts`
- Test: `packages/quasar/test/boot.test.ts`

**Interfaces:**

- Consumes: `initGlitchTip`, `GlitchTipOptions` (core); `wireVueErrorHandlers`, `ObservabilityUx` (wiring).
- Produces:
  - `interface CreateObservabilityBootOptions` = `Omit<GlitchTipOptions,'dsn'> & { dsn?: string; ux?: ObservabilityUx }`
  - `createObservabilityBoot(opts): <Quasar boot default export>`
  - re-exports `ObservabilityUx`, `ErrorContext`, `wireVueErrorHandlers`

- [ ] **Step 1: Write the failing test**

`packages/quasar/test/boot.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const init = vi.fn();
const wire = vi.fn();
vi.mock("@epfl-enac/observability-core", () => ({
  initGlitchTip: (...a: unknown[]) => init(...a),
}));
vi.mock("../src/wiring", () => ({
  wireVueErrorHandlers: (...a: unknown[]) => wire(...a),
}));
// Quasar's boot() just returns the callback it is given.
vi.mock("quasar/wrappers", () => ({ boot: (cb: unknown) => cb }));

import { createObservabilityBoot } from "../src/index";

const app = {} as never;
const router = {} as never;

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("createObservabilityBoot", () => {
  it("inits the reporter when a DSN is present and always wires handlers", () => {
    const bootFn = createObservabilityBoot({
      dsn: "https://k@h/1",
      environment: "prod",
    });
    bootFn({ app, router } as never);
    expect(init).toHaveBeenCalledWith(
      expect.objectContaining({ dsn: "https://k@h/1", environment: "prod" }),
    );
    expect(wire).toHaveBeenCalledWith(expect.objectContaining({ app, router }));
  });

  it("skips init when no DSN but still wires handlers", () => {
    const bootFn = createObservabilityBoot({});
    bootFn({ app, router } as never);
    expect(init).not.toHaveBeenCalled();
    expect(wire).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -w @epfl-enac/observability-quasar -- boot`
Expected: FAIL (`src/index.ts` has no `createObservabilityBoot`).

- [ ] **Step 3: Write `packages/quasar/src/index.ts`**

```ts
import { boot } from "quasar/wrappers";
import {
  initGlitchTip,
  type GlitchTipOptions,
} from "@epfl-enac/observability-core";
import {
  wireVueErrorHandlers,
  type ErrorContext,
  type ObservabilityUx,
} from "./wiring";

export interface CreateObservabilityBootOptions extends Omit<
  GlitchTipOptions,
  "dsn"
> {
  // No DSN (dev, CI, unconfigured deploys) → reporter init is skipped and the
  // handlers report nowhere, but wiring is still installed.
  dsn?: string;
  ux?: ObservabilityUx;
}

// Build a Quasar boot default-export that inits the reporter (when a DSN is
// given) and wires the Vue/router/window handlers.
export function createObservabilityBoot(opts: CreateObservabilityBootOptions) {
  const { dsn, ux, ...reporter } = opts;
  return boot(({ app, router }) => {
    if (dsn) initGlitchTip({ ...reporter, dsn });
    wireVueErrorHandlers({ app, router, ux });
  });
}

export { wireVueErrorHandlers };
export type { ObservabilityUx, ErrorContext };
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -w @epfl-enac/observability-quasar -- boot`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/quasar/src/index.ts packages/quasar/test/boot.test.ts
git commit -m "feat(quasar): createObservabilityBoot factory"
```

---

### Task 7: Quasar package — default UX adapter (`/ux` entry)

**Files:**

- Create: `packages/quasar/src/ux.ts`
- Test: `packages/quasar/test/ux.test.ts`

**Interfaces:**

- Consumes: `ObservabilityUx`, `ErrorContext` (wiring); Quasar `Notify`.
- Produces:
  - `interface QuasarNotifyUxOptions { t; isHandled?; notifyOptions?; reloadKey?; reloadActionKey? }`
  - `createQuasarNotifyUx(opts): ObservabilityUx`

- [ ] **Step 1: Write the failing test**

`packages/quasar/test/ux.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const notify = vi.fn();
vi.mock("quasar", () => ({
  Notify: { create: (...a: unknown[]) => notify(...a) },
}));

import { createQuasarNotifyUx } from "../src/ux";

const t = (k: string) => `t:${k}`;

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("createQuasarNotifyUx", () => {
  it("toasts an error message", () => {
    const ux = createQuasarNotifyUx({ t });
    ux.onError!(new Error("broke"), { mechanism: "vue", info: "render" });
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ color: "negative", message: "broke" }),
    );
  });

  it("suppresses the toast when isHandled returns true", () => {
    const ux = createQuasarNotifyUx({ t, isHandled: () => true });
    ux.onError!(new Error("already toasted"), {
      mechanism: "onunhandledrejection",
    });
    expect(notify).not.toHaveBeenCalled();
  });

  it("shows a sticky reload prompt once for chunk-load errors", () => {
    const ux = createQuasarNotifyUx({ t });
    ux.onChunkLoadError!(new Error("Loading chunk 1 failed"));
    ux.onChunkLoadError!(new Error("Loading chunk 2 failed"));
    expect(notify).toHaveBeenCalledTimes(1);
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "t:new_version_available",
        timeout: 0,
      }),
    );
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -w @epfl-enac/observability-quasar -- ux`
Expected: FAIL (`src/ux.ts` does not exist).

- [ ] **Step 3: Write `packages/quasar/src/ux.ts`**

```ts
import { Notify, type QNotifyCreateOptions } from "quasar";
import type { ErrorContext, ObservabilityUx } from "./wiring";

export interface QuasarNotifyUxOptions {
  // App i18n translate fn — no hardcoded strings live in this package.
  t: (key: string) => string;
  // Return true for errors already surfaced elsewhere (e.g. a ky HTTPError the
  // API layer already toasted) so we don't double-toast.
  isHandled?: (err: unknown) => boolean;
  // Styling/behavior overrides merged into the error toast.
  notifyOptions?: QNotifyCreateOptions;
  // i18n keys for the chunk-load reload prompt.
  reloadKey?: string;
  reloadActionKey?: string;
}

function messageOf(err: unknown): string {
  return err instanceof Error
    ? err.message
    : ((err as { message?: string } | null)?.message ?? String(err));
}

// Default UX layer reproducing co2-calculator's behavior: a negative toast on
// each error and a single sticky "new version, reload?" prompt on chunk-load.
// Opt-in (only used if the app passes it as `ux`) and parameterized.
export function createQuasarNotifyUx(
  opts: QuasarNotifyUxOptions,
): ObservabilityUx {
  const {
    t,
    isHandled,
    notifyOptions,
    reloadKey = "new_version_available",
    reloadActionKey = "reload",
  } = opts;

  // Guard so a burst of chunk errors (one per failed prefetch) shows one toast.
  let reloadShown = false;

  return {
    onError(err: unknown, _ctx: ErrorContext) {
      if (isHandled?.(err)) return;
      Notify.create({
        color: "negative",
        message: messageOf(err),
        position: "top",
        timeout: 5000,
        actions: [{ icon: "close", color: "white" }],
        ...notifyOptions,
      });
    },
    onChunkLoadError() {
      if (reloadShown) return;
      reloadShown = true;
      Notify.create({
        color: "info",
        message: t(reloadKey),
        position: "top",
        timeout: 0, // sticky until the user acts
        actions: [
          {
            label: t(reloadActionKey),
            color: "white",
            handler: () => window.location.reload(),
          },
        ],
      });
    },
  };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -w @epfl-enac/observability-quasar -- ux`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/quasar/src/ux.ts packages/quasar/test/ux.test.ts
git commit -m "feat(quasar): createQuasarNotifyUx default UX adapter"
```

---

### Task 8: Quasar package — Vite build (two entries) + verify exports

**Files:**

- Create: `packages/quasar/vite.config.ts`

**Interfaces:**

- Consumes: the quasar source.
- Produces: `dist/index.js`, `dist/ux.js`, and matching `.d.ts`, with `quasar`/`vue`/`vue-router`/core left external.

- [ ] **Step 1: Write `packages/quasar/vite.config.ts`**

```ts
import { resolve } from "node:path";
import { defineConfig } from "vite";
import dts from "vite-plugin-dts";

export default defineConfig({
  build: {
    lib: {
      entry: {
        index: resolve(__dirname, "src/index.ts"),
        ux: resolve(__dirname, "src/ux.ts"),
      },
      formats: ["es"],
    },
    rollupOptions: {
      // Never bundle the framework or the core package into the adapter.
      external: [
        "vue",
        "vue-router",
        "quasar",
        "quasar/wrappers",
        "@epfl-enac/observability-core",
      ],
    },
  },
  plugins: [dts({ include: ["src"] })],
  test: { environment: "jsdom" },
});
```

- [ ] **Step 2: Build and verify both entries emit**

Run: `npm run build -w @epfl-enac/observability-quasar`
Expected: PASS; `dist/index.js`, `dist/ux.js`, `dist/index.d.ts`, `dist/ux.d.ts` all exist.

- [ ] **Step 3: Verify core is not inlined into the bundle**

Run: `grep -c "envelope" packages/quasar/dist/index.js || true`
Expected: `0` — the reporter internals stay in core, imported, not copied.

- [ ] **Step 4: Full workspace build + test as a regression gate**

Run: `npm run build && npm test`
Expected: both packages build; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/quasar/vite.config.ts
git commit -m "build(quasar): Vite library build with index + ux entries"
```

---

### Task 9: CI workflow (PR checks)

**Files:**

- Create: `.github/workflows/ci.yml`

**Interfaces:**

- Consumes: root `build`/`test`/`typecheck`/`lint` scripts.
- Produces: a PR gate running on every push/PR.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: "npm" }
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run build
      - run: npm test
```

- [ ] **Step 2: Generate `package-lock.json` so `npm ci` works in CI**

Run: `npm install`
Expected: `package-lock.json` present at the repo root.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml package-lock.json
git commit -m "ci: build, typecheck, lint and test on PR"
```

---

### Task 10: Publish workflow (tag → GitHub Packages)

**Files:**

- Create: `.github/workflows/publish.yml`

**Interfaces:**

- Consumes: each package's `build` script + `publishConfig`.
- Produces: `npm publish` of both packages on a pushed tag.

- [ ] **Step 1: Write `.github/workflows/publish.yml`**

```yaml
name: Publish
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://npm.pkg.github.com'
          scope: '@epfl-enac'
      - run: npm ci
      - run: npm run build
      - run: npm publish --workspace @epfl-enac/observability-core --access restricted
        env: { NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
      - run: npm publish --workspace @epfl-enac/observability-quasar --access restricted
        env: { NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
```

- [ ] **Step 2: Document the release procedure in the root `README.md`**

Append:

```markdown
## Releasing

1. Bump the changed package(s): `npm version <patch|minor|major> -w <pkg>`.
2. Commit and push.
3. Tag and push the tag: `git tag vX.Y.Z && git push --tags`.
   The Publish workflow builds and publishes both packages to GitHub Packages.
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish.yml README.md
git commit -m "ci: publish packages to GitHub Packages on tag"
```

---

### Task 11: Per-package READMEs + co2-calculator migration note

**Files:**

- Create: `packages/core/README.md`
- Create: `packages/quasar/README.md`
- Create: `docs/migrating-co2-calculator.md`

**Interfaces:**

- Consumes: the finished public APIs.
- Produces: usage docs and a written migration recipe (the migration itself is a separate effort, not executed here).

- [ ] **Step 1: Write `packages/core/README.md`**

````markdown
# @epfl-enac/observability-core

Framework-agnostic GlitchTip/Sentry-compatible error reporter. Zero deps.

```ts
import { initGlitchTip, captureError } from "@epfl-enac/observability-core";

initGlitchTip({ dsn, environment, release, ignoreErrors });
captureError(new Error("boom"), { mechanism: "manual" });
```

Exports: `initGlitchTip`, `captureError`, `addBreadcrumb`,
`startNavigationTrace`, `isChunkLoadError`.
````

- [ ] **Step 2: Write `packages/quasar/README.md`**

````markdown
# @epfl-enac/observability-quasar

Quasar boot wiring for `@epfl-enac/observability-core`, with an optional
batteries-included UX layer.

Create a boot file in your app (`src/boot/observability.ts`):

```ts
import { createObservabilityBoot } from "@epfl-enac/observability-quasar";
import { createQuasarNotifyUx } from "@epfl-enac/observability-quasar/ux";

export default createObservabilityBoot({
  dsn: runtimeConfig.sentryDsn,
  environment: runtimeConfig.environment,
  release: runtimeConfig.release,
  ignoreErrors,
  ux: createQuasarNotifyUx({ t: i18n.global.t }),
});
```

Omit `ux` for pure wiring (no toasts). Pass `isHandled` to suppress
double-toasts for errors your API layer already surfaced.
````

- [ ] **Step 3: Write `docs/migrating-co2-calculator.md`**

```markdown
# Migrating co2-calculator to the shared packages

This is a follow-up to creating the packages — do it once they are published.

1. Add deps:
   `npm i @epfl-enac/observability-core @epfl-enac/observability-quasar`
2. Delete `frontend/src/utils/glitchtip.ts`; update imports to
   `@epfl-enac/observability-core`.
3. Replace `frontend/src/boot/sentry.ts` body with `createObservabilityBoot`,
   passing `createQuasarNotifyUx({ t: i18n.global.t, isHandled: (e) => e instanceof HTTPError })`
   to reproduce today's toasts, reload prompt, and HTTPError double-toast
   suppression. Keep `ignoreErrors` in the app and pass it through.
4. Delete the local `isChunkLoadError` (now from core).
5. The dev-only `window.__gtTest` console harness stays in the app's boot file.
6. Verify `make type-check` (vue-tsc) passes before committing.
```

- [ ] **Step 4: Commit**

```bash
git add packages/core/README.md packages/quasar/README.md docs/migrating-co2-calculator.md
git commit -m "docs: usage READMEs and co2-calculator migration recipe"
```

---

## Self-Review Notes

- **Spec coverage:** core lift (T2), `isChunkLoadError` relocation (T3), zero-dep ESM build (T4), minimal wiring layer (T5), boot factory (T6), parameterized default UX as `/ux` second entry (T7), tree-shakeable two-entry build (T8), npm-workspaces/Vite/Vitest tooling (T1/T4/T8), GitHub Packages publish under `@epfl-enac` (T10), migration recipe (T11). All spec sections map to a task.
- **Vitest no-vitest caveat:** applies only to co2-calculator's harness; this standalone repo uses Vitest (T2/T5/T6/T7) per the spec.
- **Type consistency:** `ObservabilityUx`/`ErrorContext` defined in T5 (`wiring.ts`), consumed unchanged in T6 and T7. `createObservabilityBoot` / `createQuasarNotifyUx` / `wireVueErrorHandlers` / `isChunkLoadError` names are stable across tasks.
- **`tsgo`:** intentionally not in the build path (preview; declaration emit not yet trusted for a published contract). Optional future fast-typecheck only.
