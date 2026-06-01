# Bot Review TODOs: PR #1322

## Source Branch: `feat/217-openapi-typescript-typegen`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR introduces a proof-of-concept OpenAPI → TypeScript type generation workflow in the frontend using `openapi-typescript`, and demonstrates the approach by migrating the auth store’s `User` shape to derive from the generated `UserRead` schema (surfacing the `id: string → number` drift).

**Changes:**

- Add `openapi-typescript` + a generator script with live-URL fetch and snapshot fallback, and wire it via npm script + Makefile target.
- Commit the generated `frontend/src/types/api/openapi.d.ts` for IDE/type-check support without the backend running.
- Migrate `frontend/src/stores/auth.ts` `User` typing to use `components['schemas']['UserRead']` with local overrides for widened fields.

### Reviewed changes

Copilot reviewed 8 out of 11 changed files in this pull request and generated 2 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                            | Description                                                                                           |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| frontend/src/types/api/openapi.d.ts                             | Adds committed generated OpenAPI declaration types for frontend consumption.                          |
| frontend/src/stores/auth.ts                                     | Replaces the hand-maintained `User` interface with a generated-schema-derived type + local overrides. |
| frontend/scripts/gen-api-types.mjs                              | Adds a Node script to generate `openapi.d.ts` from live OpenAPI or a committed snapshot.              |
| frontend/package.json                                           | Adds `openapi-typescript` devDependency and `gen-api-types` npm script.                               |
| frontend/package-lock.json                                      | Locks the new dev dependency and its transitive deps.                                                 |
| frontend/Makefile                                               | Adds `make gen-api-types` wrapper target.                                                             |
| frontend/eslint.config.js                                       | Enables Node globals for scripts and ignores the generated `openapi.d.ts`.                            |
| frontend/.prettierignore                                        | Excludes generated `openapi.d.ts` and OpenAPI snapshot from formatting churn.                         |
| docs/src/implementation-plans/217-openapi-typescript-typegen.md | Documents the tool survey, approach, and POC scope/roadmap.                                           |
| .prettierignore                                                 | Mirrors ignores at repo root for consistent formatting behavior.                                      |

</details>

<details>
<summary>Files not reviewed (1)</summary>

- **frontend/package-lock.json**: Language not supported
</details>

---

### File: `frontend/scripts/gen-api-types.mjs` (Line 71) — github-advanced-security[bot]

## CodeQL / Network data written to file

Write to file system depends on [Untrusted data](1).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/674)

### File: `frontend/src/stores/auth.ts` (Line 47) — Copilot

## `roles_raw` is declared optional here, but other consumers treat it as always present (e.g. route guards call `.map(...)` on it). Since the backend uses `response_model_exclude_none=True`, `roles_raw` can be omitted when null, which would crash those call sites at runtime. Consider normalizing `roles_raw` to an empty array when hydrating the user (or keeping it non-optional in the local `User` type and enforcing that invariant in `getUser()`).

### File: `frontend/scripts/gen-api-types.mjs` (Line null) — Copilot

The generator shells out via plain `npx openapi-typescript ...`. To keep this deterministic/offline-friendly (and to ensure the repo-pinned devDependency is used), prefer `npm exec -- openapi-typescript ...` or `npx --no-install openapi-typescript ...`. This avoids interactive prompts / network installs if someone runs the script before dependencies are installed or has a global version on PATH.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **frontend/scripts/gen-api-types.mjs (L71)** — CodeQL "network data written to file": verdict **wrong (false positive)**. The fetched OpenAPI JSON is written to a fixed `mkdtempSync` path; the untrusted _content_ never influences the _path_, so there is no traversal/arbitrary-write. Source is the project's own FastAPI backend, and this is a dev-only build script. Fix: dismiss alert #674 on the security tab as "won't fix / false positive" with that rationale. Not merge-blocking (CodeQL rollup is NEUTRAL).

_The two Copilot comments (`roles_raw` optionality, `npx` pinning) were both already addressed in commit `99ac554c` — dropped as already-fixed._
