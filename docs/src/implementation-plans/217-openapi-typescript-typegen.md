---
status: delivered
issue: 217
last_updated: 2026-05-28
title: "Implementation Plan: Auto-generate TypeScript types from FastAPI OpenAPI"
summary: "Stand up a POC that pipes the FastAPI OpenAPI 3.1 schema into a generated `openapi.d.ts` consumed by the existing `ky` HTTP client. Recommends `openapi-typescript` over heavier SDK generators, ships the generator script, makefile target, committed snapshot, and a single migrated interface (`User`) as proof."
---

# Implementation Plan: Auto-generate TypeScript types from FastAPI OpenAPI

## Overview

The frontend currently hand-maintains every API response shape inline in
store files (`frontend/src/stores/auth.ts`, `workspace.ts`,
`backoffice.ts`, …). The backend exposes a complete OpenAPI 3.1 schema at
`/api/openapi.json` (80 routes, 71 component schemas), but nothing reads
it. As routes and Pydantic models evolve the hand-typed shapes silently
drift — for example the existing `User.id` is typed `string` even though
the backend emits `integer` (`UserBase.id: Optional[int]`,
`UserRead.id` resolves to `number` in the generated schema). This POC
pulls the OpenAPI schema into a generated `.d.ts` and migrates one
interface to prove the ergonomics end-to-end.

## Goals (in scope for this PR)

1. Survey the four credible OpenAPI-to-TypeScript tools in 2026 and
   pick one with a documented rationale.
2. Ship the generator: dev dependency, script, Makefile target.
3. Commit a snapshot of `openapi.json` and the generated `openapi.d.ts`
   so IDE support and `make type-check` work without running the
   backend.
4. Migrate exactly one hand-maintained interface (`User` in
   `frontend/src/stores/auth.ts`) as the worked example.

## Non-goals (deferred to follow-up PRs)

- CI step that regenerates types and fails the build on drift. Once the
  team is comfortable regenerating locally, a `make gen-api-types &&
git diff --exit-code src/types/api/openapi.d.ts` check belongs in the
  existing frontend CI workflow.
- Migrating the remaining hand-maintained interfaces across
  `stores/workspace.ts`, `stores/backoffice.ts`, `api/audit.ts`,
  `api/locations.ts`, etc. Best handled module-by-module by the owners
  of each domain; the pattern this PR establishes carries over directly.
- Replacing the `ky` HTTP client. The recommendation is deliberately
  types-only — keeping `ky` means no behavioural change.

---

## 1. Tool survey (2026)

Four candidates evaluated. All four are mature and actively maintained;
the differentiators are output shape, install footprint, and how
intrusive they are on the existing `ky`-based HTTP layer.

| Tool                                      | Output style                                                 | Install footprint                                    | OpenAPI 3.1 / Pydantic 2                        | Runtime client compatibility              | Maintenance (2026)                                 |
| ----------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------- | ----------------------------------------------- | ----------------------------------------- | -------------------------------------------------- |
| **`openapi-typescript`** (drwpow)         | Pure `.d.ts`, zero runtime cost                              | One dev dep (~33 transitive), ~80ms run time         | Yes — OpenAPI 3.0 and 3.1                       | Any. Slots into `ky`, `fetch`, `axios`, … | Actively maintained, v7.13.0 at time of writing    |
| **`@hey-api/openapi-ts`**                 | Full SDK: client, types, optional zod, fetch wrappers        | Multi-package; configured via `openapi-ts.config.ts` | Yes                                             | Replaces the HTTP client with its own SDK | Actively maintained, broad plugin ecosystem        |
| **`orval`**                               | Generates TanStack/Vue Query hooks, MSW mocks                | Heavyweight; opinionated framework integrations      | Yes                                             | Replaces both HTTP client and call sites  | Actively maintained, popular in React Query stacks |
| **`@openapitools/openapi-generator-cli`** | Templated Java-based generator (typescript-fetch, -axios, …) | Pulls a JRE; slow startup                            | Mostly yes; 3.1 support uneven across templates | Replaces HTTP client                      | Active; generic, less TS-idiomatic than the others |

### Why `openapi-typescript`

- **Drop-in for the existing `ky` client.** It only emits types. The
  HTTP call sites stay exactly as written today
  (`api.get(API_ME_URL).json<User>()`); the only change is where `User`
  comes from. None of the other three deliver that — they all generate
  their own call layer.
- **Smallest blast radius.** One dev dep, one declaration file, no
  runtime code. If the team later changes its mind, ripping it out is
  `rm -rf src/types/api && npm uninstall openapi-typescript`.
- **Fast.** ~80ms for our 80-route, 71-schema spec. Suitable for a
  pre-commit or CI drift check without slowing the loop.
- **OpenAPI 3.1 / Pydantic 2 native.** FastAPI 0.136 emits 3.1; this
  matches.

### Why not the others

- **`@hey-api/openapi-ts`** generates a full SDK. Switching from `ky` to
  a generated SDK is a separate, much larger decision; doing it under
  the banner of "type generation" would conflate two changes. Worth
  revisiting if/when we want generated mutation hooks.
- **`orval`** is genuinely excellent when you're already on TanStack
  Query. We're not — Pinia stores still own data fetching — so its
  framework integrations would be wasted weight.
- **`openapi-generator-cli`** drags a JRE into the dev toolchain and
  emits less idiomatic TypeScript than tools written natively in TS.
  Only justified if we needed cross-language generation (Java/Go/Rust
  clients in the same repo); we don't.

---

## 2. POC implementation

### Files added

| Path                                                              | Purpose                                                   |
| ----------------------------------------------------------------- | --------------------------------------------------------- |
| `frontend/scripts/gen-api-types.mjs`                              | Node ESM generator: live URL with snapshot fallback       |
| `frontend/scripts/openapi.snapshot.json`                          | Committed snapshot for offline / pre-backend regeneration |
| `frontend/src/types/api/openapi.d.ts`                             | Generated types, committed for IDE support                |
| `docs/src/implementation-plans/217-openapi-typescript-typegen.md` | This document                                             |

### Files modified

| Path                          | Change                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| `frontend/package.json`       | Add `openapi-typescript@=7.13.0` devDependency and `gen-api-types` script                  |
| `frontend/Makefile`           | Add `gen-api-types` target wrapping the npm script                                         |
| `frontend/eslint.config.js`   | Node-globals for `scripts/**`; ignore generated `src/types/api/openapi.d.ts`               |
| `frontend/src/stores/auth.ts` | Replace hand-written `User` with a thin wrapper around `components["schemas"]["UserRead"]` |

### Generator script behaviour

`scripts/gen-api-types.mjs` resolves the schema source in this order:

1. **Live backend.** Fetches `OPENAPI_URL` (default
   `http://localhost:8000/openapi.json`) with a 3 s timeout. Used when
   the backend is up locally and (later) in CI.
2. **Committed snapshot.** Falls back to
   `scripts/openapi.snapshot.json` when the live fetch fails. Keeps
   the generator usable offline and on contributor machines that don't
   have the FastAPI stack running.

Either way it shells out to `openapi-typescript` and writes
`src/types/api/openapi.d.ts`. The snapshot is regenerated by dumping
`backend/app.main.app.openapi()` (no HTTP server required).

### Worked example: migrating `User`

The hand-maintained interface in `frontend/src/stores/auth.ts` was:

```ts
interface User {
  id: string;
  email: string;
  display_name?: string;
  is_user_test?: boolean;
  institutional_id?: string;
  roles_raw: Array<{
    role: string;
    on: { unit?: string; affiliation?: string } | "global";
  }>;
  permissions?: {
    [key: string]: { view?: boolean; edit?: boolean; export?: boolean };
  };
}
```

Replaced with:

```ts
import type { FlatUserPermissions } from "src/constant/permissions";
import type { components } from "src/types/api/openapi";

type GeneratedUserRead = components["schemas"]["UserRead"];
type User = Omit<GeneratedUserRead, "permissions" | "roles_raw"> & {
  permissions?: FlatUserPermissions;
  roles_raw?: Array<{
    role: string;
    on: { unit?: string; affiliation?: string } | "global";
  }>;
};
```

Why the wrapper (and not the bare generated type):

- The backend's `UserRead.permissions` and `UserRead.roles_raw` are
  declared with `additionalProperties: true` (computed Pydantic fields)
  and serialize to `unknown` in the generated schema. The runtime
  shape is narrower — `FlatUserPermissions` and the typed
  `roles_raw` array — and that narrower shape is what permission
  helpers (`hasPermission`, `hasAnyScopePermission`, …) and
  `authGuard.ts` actually consume. Using the bare generated type would
  push `as` casts to every call site.
- Everything else (`id: number`, `email: string`, `display_name`,
  `institutional_id`, `is_user_test`, `last_login`, `provider`) flows
  through `Omit` so backend changes to those fields immediately
  surface in TypeScript.

#### Drift surfaced by this migration

The pre-existing hand-typed `id: string` was wrong. The backend emits
`UserBase.id: Optional[int]` and `UserRead.id` is `integer` in the
schema. The migration silently fixes this — `user.value.id` is now
`number`. The only consumer is the display-name fallback
`user.value.id || '?'` in the same store; that still works (the only
falsy `number` is `0`, which is never a real user id).

### Verification

- `cd frontend && make type-check` — passes.
- `cd frontend && make lint` — passes.
- `cd frontend && make gen-api-types` — regenerates
  `src/types/api/openapi.d.ts` from the committed snapshot in ~80 ms;
  output is byte-identical to the committed file (lint stable).

---

## 3. POC limitations and follow-ups

### POC uses a committed snapshot for the generator's input

Generating from a committed `openapi.snapshot.json` is intentional for
the POC: it lets reviewers and contributors verify the toolchain
without standing up postgres + alembic + uvicorn. The generator does
try the live backend first, so the live path is already exercised — it
just falls back to the snapshot when nothing is listening.

The follow-up CI integration will:

1. Stand up the backend in the same workflow that already runs
   `make type-check`.
2. Re-run `make gen-api-types` against the live `/openapi.json`.
3. Fail the build if `git diff --exit-code src/types/api/openapi.d.ts`
   reports a delta — i.e. someone changed a Pydantic schema without
   regenerating the frontend types.

The snapshot stays in the repo as a fallback for offline contributors
and as a sanity reference for what the schema looked like at any given
commit.

### Migration roadmap (separate PRs)

Once this POC merges, hand-maintained API interfaces can be replaced
incrementally, one module at a time. Suggested order based on
churn-vs-value:

1. `frontend/src/stores/workspace.ts` — Unit list, selected unit.
2. `frontend/src/stores/backoffice.ts` — Backoffice user list,
   roles, role-assignment payloads.
3. `frontend/src/api/audit.ts` — Audit log entries (rich nested
   schemas — biggest drift risk).
4. `frontend/src/api/locations.ts`, `api/modules.ts` — Reference data.

Each migration uses the same `Omit + override` pattern wherever a
computed-field or `additionalProperties: true` shape is involved, or
the bare `components["schemas"][...]` import where the schemas are
fully typed.

### Closes #217 (POC + research)
