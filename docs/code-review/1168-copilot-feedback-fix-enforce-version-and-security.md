# Bot Review TODOs: PR #1168

## Source Branch: `fix/enforce-version-and-security`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR tightens Node/npm version consistency and dependency pinning across the repo, and updates CI/Docker/Dependabot configuration to support more reproducible and security-conscious installs.

**Changes:**

- Pinned root + frontend dependencies (and some overrides) to exact versions; added `packageManager` and strict `engines`.
- Added repo and frontend `.nvmrc` and updated GitHub Actions workflows to use `.nvmrc` for Node setup (plus Corepack enablement).
- Added `.npmrc` settings (`ignore-scripts=true`, `engine-strict=true`), new setup scripts, and refactored the frontend Dockerfile into a multi-stage build with caching.

### Reviewed changes

Copilot reviewed 14 out of 16 changed files in this pull request and generated 5 comments.

<details>
<summary>Show a summary per file</summary>

| File                                | Description                                                                            |
| ----------------------------------- | -------------------------------------------------------------------------------------- |
| package.json                        | Adds setup scripts and enforces Node/npm versions; pins devDependencies.               |
| package-lock.json                   | Aligns lockfile with pinned versions and new engines metadata.                         |
| Makefile                            | Routes install through `npm run setup` and adds basic Node presence/version output.    |
| frontend/package.json               | Pins frontend deps/devDeps/overrides; enforces Node/npm versions and package manager.  |
| frontend/package-lock.json          | Updates frontend lockfile to match pinned dependencies.                                |
| frontend/Dockerfile                 | Converts to multi-stage build with Corepack enablement and npm cache mount.            |
| frontend/.nvmrc                     | Adds Node version pin for frontend tooling.                                            |
| frontend/.npmrc                     | Enforces ignore-scripts + engine-strict for frontend installs.                         |
| .nvmrc                              | Adds root Node version pin.                                                            |
| .npmrc                              | Enforces ignore-scripts + engine-strict for root installs.                             |
| .github/workflows/test.yml          | Uses `.nvmrc` for Node version and enables Corepack; installs with `--ignore-scripts`. |
| .github/workflows/security.yml      | Uses `.nvmrc` for Node version consistency.                                            |
| .github/workflows/quality-check.yml | Uses `.nvmrc` for Node version and enables Corepack; installs with `--ignore-scripts`. |
| .github/workflows/lighthouse.yml    | Uses `.nvmrc` for Node version and enables Corepack; installs with `--ignore-scripts`. |
| .github/workflows/changelog.yml     | Bumps Node requirement (but does not use `.nvmrc`).                                    |
| .github/dependabot.yml              | Adds cooldown and increases open PR limits (per PR description).                       |

</details>

---

### File: `package.json` (Line 5) — Copilot

Because repo-level .npmrc sets ignore-scripts=true, the `npm rebuild lefthook` in `setup`/`setup:fresh` will also skip lefthook’s install scripts. Since lefthook is marked `hasInstallScript: true` in package-lock, this can leave lefthook unusable and make `npx lefthook install`/`npm run lint` fail. Override ignore-scripts for the rebuild step (e.g., set npm_config_ignore_scripts=false for that command) or avoid a global ignore-scripts in .npmrc and enforce it only for `npm ci`.

---

### File: `Makefile` (Line 69) — Copilot

`npm run setup` already runs `npx lefthook install`, but the Makefile calls `npx lefthook install` again immediately after. This duplication adds confusion and can mask failures in the setup script—consider removing one of the two so there is a single source of truth for hook installation.

---

### File: `frontend/Dockerfile` (Line 4) — Copilot

The Dockerfile uses `node:24-alpine`, which will float to the latest Node 24 patch and can drift from the enforced `.nvmrc`/engines version (24.15.0). To keep builds reproducible and aligned with CI/dev, pin the image to the same patch version (e.g., `node:24.15.0-alpine`).

---

### File: `.github/workflows/changelog.yml` (Line 30) — Copilot

## This workflow is now using a hardcoded range (`>=24.0.0`) instead of `node-version-file: '.nvmrc'` like the other workflows in this PR. That undermines the “single source of truth” for Node versions and can lead to drift; consider switching to `node-version-file` (or at least pinning to the exact patch in `.nvmrc`).

### File: `.github/workflows/quality-check.yml` (Line 25) — Copilot

`actions/setup-node` is caching based on `./package-lock.json`, but this job installs in `./frontend` and runs `npm ci` against `frontend/package-lock.json`. Point `cache-dependency-path` at `./frontend/package-lock.json` to avoid ineffective caching and unexpected cache misses/hits.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`package.json` + `.npmrc`** — `ignore-scripts=true` in root `.npmrc` makes the `setup` / `setup:fresh` scripts' `npm rebuild lefthook` step a no-op (lefthook's postinstall downloads its binary; without it, `npx lefthook install` fails). Fix: override per-command in the scripts, e.g. `npm ci --ignore-scripts && npm rebuild lefthook --ignore-scripts=false && npx lefthook install`. Don't drop the global `.npmrc` setting — it's load-bearing for `npm ci` hardening. Verify by deleting `node_modules` + lockfile cache locally and running `npm run setup` (should produce a working `lefthook` binary).

### Performance

- [ ] **`.github/workflows/quality-check.yml:25`** — `cache-dependency-path: "./package-lock.json"` keys the cache off the root lockfile, but the job's `npm ci` runs against `./frontend/package-lock.json` (job-level `working-directory: ./frontend`). Cache will rarely invalidate when frontend deps change, and won't refresh when actually needed. Fix: change to `"./frontend/package-lock.json"` to match the install target (test.yml and lighthouse.yml already use that path correctly).

### Maintainability / refactoring

- [ ] **`Makefile:69`** — `npx lefthook install` is called both by `npm run setup` (line 67) and directly on line 69. Fix: drop line 69; let `npm run setup` be the single source of truth for hook installation.
- [ ] **`frontend/Dockerfile:4`** — `FROM node:24-alpine` floats to the latest 24.x patch, drifting from the `.nvmrc`/`engines` pin (`24.15.0`). Fix: `FROM node:24.15.0-alpine`. Accept the tradeoff (manual bump for security patches) in exchange for reproducibility — the whole branch's premise.
- [ ] **`.github/workflows/changelog.yml:29`** — `node-version: '>=24.0.0'` is inconsistent with the other workflows that use `node-version-file: '.nvmrc'`. Fix: switch to `node-version-file: '.nvmrc'`. Low severity — this workflow only globally installs `conventional-changelog-cli` and doesn't touch project lockfiles, so the engine mismatch we just fought won't bite here — but consistency is cheap.
