---
status: delivered
issue: 1332
last_updated: 2026-06-08
title: "Lighthouse: single config + nightly cron"
summary: "Merge the duplicate Lighthouse configs into one source of truth and move CI from per-PR to a nightly cron."
---

# Lighthouse: single config + nightly cron

## Problem

Two Lighthouse config files lived in `frontend/`, but only one was
consumed:

| File                             | URLs | Consumers                             |
| -------------------------------- | ---: | ------------------------------------- |
| `frontend/.lighthouserc.json`    |   24 | none — orphan                         |
| `frontend/.lighthouserc.ci.json` |    4 | `lighthouse.yml`, `frontend/Makefile` |

Commit `768f5b98` split local vs CI configs but never wired any
consumer to the 24-URL file. Every Lighthouse run (CI and
`make lighthouse`) audited the same 4-route smoke set, so the
24-URL list silently drifted — new backoffice and simulation
routes got no coverage.

On top of that, the smoke audit ran on **every** frontend PR,
adding latency to the PR critical path for a signal that rarely
gates a merge.

## Solution

Single source of truth + move the full sweep off the PR path.

1. **One config.** Keep `frontend/.lighthouserc.json` (24 routes),
   delete `frontend/.lighthouserc.ci.json`. Both CI and
   `make lighthouse` point at the kept file. A `_comment` key inside
   `ci` names the two consumers (JSON has no comment syntax; lhci
   ignores unknown keys).
2. **Lenient assertions.** The merged file keeps the smoke config's
   thresholds — `performance ≥ 0.6`, `accessibility ≥ 0.7`,
   `best-practices ≥ 0.9`, `seo ≥ 0.9`, `color-contrast: warn` — so
   the heavier backoffice/simulation routes don't turn the nightly
   red on borderline scores.
3. **Nightly cron.** `lighthouse.yml` now mirrors
   `integration-tests.yml`: `schedule` cron at **04:00 UTC** (offset
   from integration-tests' 03:30 to avoid pileup), `workflow_dispatch`,
   and push to `ci-test/**`. The `pull_request` trigger and the
   now-dead "Comment PR with Lighthouse results" step are removed.

## What changed

- `frontend/.lighthouserc.json` — `_comment` consumer note; thresholds
  relaxed to the lenient set; `color-contrast: warn` added.
- `frontend/.lighthouserc.ci.json` — deleted.
- `frontend/Makefile` — `lighthouse` target uses `.lighthouserc.json`;
  help text updated to "24 routes".
- `.github/workflows/lighthouse.yml` — cron/dispatch/ci-test trigger;
  `configPath` → `.lighthouserc.json`; PR-comment step removed.
- `docs/src/architecture/cicd-workflows.md` — workflow + troubleshooting
  entries updated to the nightly/single-config reality.

## Verification

- `cd frontend && make lighthouse` audits the 24-route list.
- Nightly workflow (or `workflow_dispatch`) audits the same 24 routes
  against `.lighthouserc.json`; no longer runs on PRs.
- No dangling references to `.lighthouserc.ci.json` outside historical
  plan `264-lighthouse-route-in-frontend.md` (left as a record of its
  era).
