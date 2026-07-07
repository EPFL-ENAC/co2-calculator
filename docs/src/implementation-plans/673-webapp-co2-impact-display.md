---
status: proposed
issue: 673
last_updated: 2026-07-07
title: "Homepage tooltip: webapp's own Lighthouse/ecoindex footprint"
summary: "Surface the nightly Lighthouse/ecoindex audit of the homepage as a small info tooltip in the homepage welcome header."
---

# Homepage tooltip: webapp's own Lighthouse/ecoindex footprint

## Problem

Issue #673 asks for a small tooltip on the homepage showing the
webapp's own carbon/energy footprint, sourced from Lighthouse. No
such indicator exists today.

Research into what's already available:

- `.github/workflows/lighthouse.yml` runs `lighthouse-ci-action`
  **nightly only** (04:00 UTC cron + `workflow_dispatch`), auditing
  24 routes from `frontend/.lighthouserc.json` (see
  `docs/src/implementation-plans/1332-lighthouse-config-dedup.md`).
  It already installs `lighthouse-plugin-ecoindex-core`, which scores
  each audited page's actual environmental footprint (ecoindex grade,
  grams CO2e per page view, water use) — a more direct match for
  "CO2 impact" than the raw Lighthouse performance score.
- Results today go to `uploadArtifacts: true` (GitHub Actions
  artifact, expires) and `temporaryPublicStorage: true` (an ephemeral
  public URL). Nothing is persisted anywhere the running frontend can
  fetch, and there is no LHCI server or database table for scores.
- The homepage "welcome box" is the header block in
  `frontend/src/pages/app/HomePage.vue` (`section.co2-calculator`,
  `~L138-158`): icon + `<h1>{{ $t('co2_calculator_title') }}</h1>`.
  That's the natural anchor for a small info icon + tooltip.
  (`home_title` in `frontend/src/i18n/home.ts` is dead/unused copy —
  not the render target.)

## Design

Keep this a static, nightly-refreshed number — not a live monitoring
system. The issue only asks for "little tooltip... based on
Lighthouse info," not real-time telemetry.

1. **CI extracts one summary, nightly.** In `lighthouse.yml`, after
   the existing `lighthouse-ci-action` step, add a step that reads
   the `.lighthouseci/` results for the homepage route (`/` or
   whichever URL in `.lighthouserc.json` maps to the app home) and
   writes a small flat JSON:
   ```json
   {
     "auditedAt": "2026-07-07T04:00:00Z",
     "performanceScore": 0.87,
     "ecoindexGrade": "B",
     "gCo2ePerVisit": 1.2
   }
   ```
   Field names/values depend on what `lighthouse-plugin-ecoindex-core`
   actually emits in the LHR JSON (`audits['ecoindex']` or similar) —
   confirm exact audit id during implementation.
2. **Static asset, no backend.** Commit that JSON to
   `frontend/public/lighthouse-summary.json` from the same workflow
   run (bot commit, scoped to that single file, only on the scheduled
   run — not on `workflow_dispatch`/`push` to avoid noisy commits from
   ad-hoc runs). Quasar serves `public/` as-is, so the built SPA
   exposes it at `/lighthouse-summary.json` with zero backend or API
   changes. This keeps "backend is source of truth" intact for actual
   app data — this is static CI-generated metadata, not a computed
   business value.
3. **Frontend fetch + tooltip.** On `HomePage.vue` mount, fetch
   `/lighthouse-summary.json` (plain `fetch`, no store/API client
   needed — it's a static file, not a backend endpoint). On success,
   render a small `q-icon name="o_eco"` next to the existing
   `o_calculate` icon in the header row, with a `q-tooltip` showing
   grade + gCO2e/visit + audit date (i18n'd label, translated date).
   On fetch failure or missing file (e.g. local dev, first deploy
   before the first nightly run), render nothing — no fabricated
   score, no loading spinner, just absence (consistent with "no
   silent fallbacks": we don't fake data, we just don't show the
   widget).
4. **No new component abstraction.** This is ~15 lines inline in
   `HomePage.vue` (a computed + a small template block), matching the
   existing tooltip usage pattern already in the codebase (e.g.
   `frontend/src/components/molecules/BigNumber.vue`,
   `PipelineDiagnosticTooltip.vue`). No new composable, no Pinia
   store, no polling.

## Steps

- [ ] Confirm the exact LHR audit key(s) `lighthouse-plugin-ecoindex-core`
      writes (grade, gCO2e, water) by inspecting a local
      `make lighthouse` run's `.lighthouseci/` output.
- [ ] Identify which of the 24 `.lighthouserc.json` URLs corresponds to
      the logged-in homepage (or add it if not currently audited).
- [ ] Add an extraction step to `.github/workflows/lighthouse.yml` that
      parses that route's result into `frontend/public/lighthouse-summary.json`.
- [ ] Add a scoped bot-commit step (only on `schedule` trigger) to push
      the updated JSON file.
- [ ] Add `lighthouse-summary.json` fetch + tooltip markup to
      `frontend/src/pages/app/HomePage.vue`, with i18n strings in
      `frontend/src/i18n/home.ts` (en/fr).
- [ ] Handle fetch failure / missing file by simply not rendering the
      icon (no fallback text, no cached stale placeholder).
- [ ] Manually trigger the workflow (`workflow_dispatch`) once to seed
      the initial `lighthouse-summary.json`, verify the tooltip renders
      against real data.
- [ ] Update `docs/src/architecture/cicd-workflows.md` Lighthouse entry
      to note the new summary-file output.
