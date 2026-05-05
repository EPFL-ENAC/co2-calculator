# Bot Review TODOs: PR #1006
Source Branch: `docs/860-a4-data-management-move`
---
## Raw Feedback
### Summary Feedback (copilot-pull-request-reviewer)
## Pull request overview

This PR relocates the Backoffice “Data Management” feature specification into the MkDocs documentation site (so it’s discoverable in rendered docs) and restructures it into smaller, topic-focused pages.

**Changes:**
- Added a new `docs/src/frontend/data-management/` section split across 5 pages (landing, architecture, flows, modules/config, API/troubleshooting) with Mermaid diagrams.
- Updated `docs/mkdocs.yml` navigation to surface the new “Data Management” subsection under “Frontend”.
- Replaced the old spec location with a short breadcrumb stub pointing to the new docs location.

### Reviewed changes

Copilot reviewed 7 out of 7 changed files in this pull request and generated 11 comments.

<details>
<summary>Show a summary per file</summary>

| File | Description |
| ---- | ----------- |
| frontend/src/pages/back-office/data-management.md | Breadcrumb stub linking readers to the new MkDocs docs location. |
| docs/src/frontend/data-management/index.md | New landing page (why/what/how) and links to sub-pages. |
| docs/src/frontend/data-management/architecture.md | Documents component/composable/store architecture and file layout. |
| docs/src/frontend/data-management/data-flows.md | Documents key flows (year config lifecycle, upload, recalculation, SSE). |
| docs/src/frontend/data-management/modules-and-config.md | Documents module/submodule model, config schema, and completeness rules. |
| docs/src/frontend/data-management/api-and-troubleshooting.md | Documents endpoints, payload examples, i18n keys, and debugging checklist. |
| docs/mkdocs.yml | Adds the “Frontend → Data Management” nav section pointing at the new pages. |
</details>





---
### File: `docs/src/frontend/data-management/index.md` (Line 8) — Copilot

These pages use YAML frontmatter (the leading `---` block), but MkDocs is not configured to parse/strip frontmatter (docs/mkdocs.yml lists markdown_extensions but does not enable `pymdownx.frontmatter`/`meta`). As a result, the frontmatter will render as visible content at the top of the page. Either enable frontmatter parsing in MkDocs or remove/convert these fields to normal page content.

---
### File: `docs/src/frontend/data-management/architecture.md` (Line 49) — Copilot

The Markdown tables in this doc use a double leading pipe (e.g. `|| Type | ...`), which renders an unintended empty first column / malformed table in many Markdown renderers. Use standard table syntax with a single leading `|` per row so the table renders correctly in MkDocs/GitHub.
---
### File: `docs/src/frontend/data-management/api-and-troubleshooting.md` (Line 27) — Copilot

The API diagram/doc lists a cancel endpoint (`POST /sync/jobs/{jobId}/cancel`), but there is no corresponding backend route under the /sync router (backend/app/api/v1/data_sync.py defines /jobs/{job_id}/stream and year job listing, but no /cancel endpoint). This makes the docs misleading; either implement the cancel endpoint or remove/update the documentation to reflect the actual cancellation behavior (if any).

---
### File: `docs/src/frontend/data-management/api-and-troubleshooting.md` (Line 102) — Copilot

The troubleshooting node references `POST /sync/jobs/id/cancel`, which is both inconsistent with the earlier `{jobId}` notation and (per current backend routes) does not exist. Please correct/remove this endpoint reference so readers don't follow a broken path.

---
### File: `docs/src/frontend/data-management/data-flows.md` (Line 154) — Copilot

The job status state diagram includes a `CANCELLED` state, but the actual IngestionState enum used by both backend and frontend only defines NOT_STARTED/QUEUED/RUNNING/FINISHED (no CANCELLED). Unless the app truly emits a separate CANCELLED state, the diagram should describe cancellation in terms of existing fields (e.g. FINISHED + result=ERROR, or a meta flag) to match reality.

---
### File: `docs/src/frontend/data-management/modules-and-config.md` (Line 86) — Copilot

The YearConfigurationResponse schema shown here does not match the backend response: backend/app/schemas/year_configuration.py defines `latest_jobs` on the response and does not include `recalculation_status` (recalculation status is exposed via GET /sync/recalculation-status instead). Please update the diagram/schema to reflect the actual API contract so frontend readers don’t implement against non-existent fields.

---
### File: `docs/src/frontend/data-management/architecture.md` (Line 6) — Copilot

This page uses YAML frontmatter (the leading `---` block), but MkDocs is not configured to parse/strip frontmatter (docs/mkdocs.yml has no `pymdownx.frontmatter`/`meta` extension enabled). This will render the frontmatter as visible text unless MkDocs is updated accordingly.

---
### File: `docs/src/frontend/data-management/data-flows.md` (Line 8) — Copilot

This page uses YAML frontmatter (the leading `---` block), but MkDocs is not configured to parse/strip frontmatter (docs/mkdocs.yml has no `pymdownx.frontmatter`/`meta` extension enabled). This will render the frontmatter as visible text unless MkDocs is updated accordingly.

---
### File: `docs/src/frontend/data-management/modules-and-config.md` (Line 8) — Copilot

This page uses YAML frontmatter (the leading `---` block), but MkDocs is not configured to parse/strip frontmatter (docs/mkdocs.yml has no `pymdownx.frontmatter`/`meta` extension enabled). This will render the frontmatter as visible text unless MkDocs is updated accordingly.

---
### File: `docs/src/frontend/data-management/api-and-troubleshooting.md` (Line 5) — Copilot

This page uses YAML frontmatter (the leading `---` block), but MkDocs is not configured to parse/strip frontmatter (docs/mkdocs.yml has no `pymdownx.frontmatter`/`meta` extension enabled). This will render the frontmatter as visible text unless MkDocs is updated accordingly.

---
### File: `docs/src/frontend/data-management/architecture.md` (Line 84) — Copilot

There is a second Markdown table later in this file that also uses `||` at the start of each row, which will render as an extra empty column / malformed table. Please normalize this table to standard Markdown table syntax as well.
---

## Action Items

PR #1006 (A4): 1 critical, 0 perf, 2 refactor; 8 dropped.

### Critical
- [ ] **`data-flows.md` line 152-154 — `Job Status Flow` mermaid shows `CANCELLED` as separate state, but `IngestionState` enum has no `CANCELLED`.** Verified in `backend/app/models/data_ingestion.py` lines 96-103 (only `NOT_STARTED`/`QUEUED`/`RUNNING`/`FINISHED`) and in `backend/app/repositories/data_ingestion.py` `cancel_job` (lines 463-502): cancellation transitions to `state=FINISHED`, `result=ERROR`, `meta.cancelled=true`, `is_current=False`. The state diagram should describe cancellation as `RUNNING|QUEUED|NOT_STARTED → FINISHED (result=ERROR, meta.cancelled=true)`, not introduce a phantom `CANCELLED` state.

### Refactor / Doc-quality
- [ ] **`api-and-troubleshooting.md` line 102 — endpoint notation drift.** Earlier mermaid (line 27) uses `POST /sync/jobs/{jobId}/cancel`, but the troubleshooting node says `POST /sync/jobs/id/cancel` (no braces, raw `id`). Endpoint exists (`backend/app/api/v1/data_sync.py:440 @router.post("/jobs/{job_id}/cancel")`); just normalize the placeholder syntax to `{jobId}` (or `{job_id}`) for consistency.
- [ ] **`modules-and-config.md` line 86 — minor type-name drift in ER diagram.** Doc shows `recalculation_status: RecalculationStatusEntry[]`. Backend (`backend/app/schemas/year_configuration.py:483`) actually returns `List[ModuleRecalculationStatusEntry]` (the per-module rollup, which itself contains `data_entry_types: List[RecalculationStatusEntry]`). Update the ER diagram entry to `ModuleRecalculationStatusEntry[]` (and optionally add the rollup → entry relationship) for accuracy.

### Dropped (false positives / nitpicks)
- YAML frontmatter rendering claim (×5: `index.md` L8, `architecture.md` L6, `data-flows.md` L8, `modules-and-config.md` L8, `api-and-troubleshooting.md` L5). User-confirmed false positive: dropped per task instructions.
- `architecture.md` L49 and L84 — `||` double-leading-pipe table claim. Verified via `grep -nE '^\\|\\|'` against the file: zero matches. Tables use standard single `|` syntax. Fabricated.
- `api-and-troubleshooting.md` L27 — "no `/sync/jobs/{jobId}/cancel` route exists." False: endpoint is defined at `backend/app/api/v1/data_sync.py:440`. (Notation-drift concern at L102 is captured separately above.)
- `modules-and-config.md` L86 — claim that backend "defines `latest_jobs` on the response" and "does not include `recalculation_status`." Both wrong: there is no `latest_jobs` field anywhere in `YearConfigurationResponse`, and `recalculation_status` IS on the response (`backend/app/schemas/year_configuration.py:483`). Type-name drift retained as a minor refactor item above.

### Verification notes
- All component citations (15 components across `pages/back-office/`, `components/organisms/data-management/`, `components/molecules/data-management/`) exist on disk; no fabricated names (unlike sister C3 `LabsPage`/`LabCard`/`AdminPage` issue). Line-count drift is minor (within ±15%, expected as code evolves).
- Composable + store API surface (`useBackofficeDataManagement`, `useYearConfigStore`) verified against `stores/backofficeDataManagement.ts` and `stores/yearConfig.ts`.

PR: none — triage only

