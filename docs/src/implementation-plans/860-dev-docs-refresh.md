---
status: delivered
issue: 860
last_updated: 2026-05-06
summary:
  20-PR refresh of developer documentation across 4 work-streams (A/B/C/F)
  consolidating, condensing, and structurally reorganizing docs/, with new frontmatter
  conventions, auto-indexing, ADR backfill, and mermaid-diagrammed architecture.
title: "#860 — Dev docs refresh & MkDocs restructure"
---

# #860 — Dev docs refresh & MkDocs restructure

> Reconstructed post-merge from the 20 PR bodies; the original delivery plan was lost
> with the Claude session that drove the batch. Captured here so the work has a trace
> independent of git history alone.

## Why

Issue #860 (`[FEAT]: fix/update dev docs`) — _"Verify that all information is up to
date and correct."_ Existing developer docs had drifted from the running system
(ADR-010 still listed Celery for jobs while the system had moved to in-process
asyncio), duplicated content across multiple files, and accumulated bloated single-
file pages well past the 10-Minute Rule. Several feature specs lived inside source
trees (`frontend/src/`) instead of `docs/`.

## Approach

Split into four work-streams sized for parallel agent execution:

- **A** — housekeeping: moves, deletions, consolidations.
- **B** — foundation: structural choices that everything else depends on
  (auto-index pipeline, frontmatter conventions, ADR backfill, nav, landing).
- **C** — condense + diagram: rewrite oversized pages around C4-style mermaid.
- **F** — follow-ups discovered during review.

Two **keystone** PRs gate the rest: **B4** (path move + frontmatter) must merge
before path-affected siblings; **B3** (nav reorder) must merge before nav-affected
siblings.

## Delivered (20 PRs, all merged 2026-05-05)

### Work-stream A — Housekeeping

| PR    | Unit    | Title                                                                                                 |
| ----- | ------- | ----------------------------------------------------------------------------------------------------- |
| #999  | A1      | Drop 3 empty user-docs stubs + nav cleanup.                                                           |
| #1007 | A2      | Consolidate database ERDs to `erd.md`; delete 3 superseded drafts.                                    |
| #1015 | A3-redo | Author `backend/csv-seed-formats.md` from provider source.                                            |
| #1006 | A4      | Move 847-line `data-management.md` from `frontend/src/` into `docs/`, split into 5 right-sized pages. |
| #1000 | A5      | Move `MISSING-QUASAR-BRIDGE.md` from `frontend/css/` into `docs/src/frontend/`.                       |

A3-redo replaced the original A3 (abandoned: source `seed_data/CSV_FORMATS.md` did
not exist on `main`); the redo writes the doc directly from
`backend/app/services/data_ingestion/csv_providers/` source code with cited line
numbers.

### Work-stream B — Foundation

| PR    | Unit | Title                                                                                                                                                                                                                |
| ----- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #1010 | B0   | Wire auto-index pipeline (`awesome-pages`, `gen-files`, `literate-nav`); `gen_indexes.py` walks `docs/src/{architecture,backend,frontend}` + plans dir.                                                              |
| #1013 | B1   | ADR refresh: flip ADR-010 Planned→Accepted (asyncio not Celery); add ADR-011/015/016/017/018.                                                                                                                        |
| #1004 | B2   | Rewrite `architecture/spec.md` as Code Requirements Document.                                                                                                                                                        |
| #1001 | B3   | Dual-persona landing page + nav reorder (Home → CRD → Architecture → ADRs → Backend → Frontend → Database → Infra → Plans → User). **Keystone for nav-dependent siblings.**                                          |
| #1014 | B4   | Backfill frontmatter on 67 implementation plans; categorize 16 delivered / 17 in-progress / 34 abandoned (archived); `git mv` plans into `docs/src/implementation-plans/`. **Keystone for path-dependent siblings.** |
| #1012 | B5   | Add `llm-agent-guide.md` + `glossary.md` (17 project-specific terms).                                                                                                                                                |

**B1 ADR additions** (slot collisions resolved against pre-existing ADR-012/013/014):
ADR-011 factor classification → JSONB · ADR-015 atomic `claim_job` · ADR-016 two-path
pipeline · ADR-017 `/me` async role sync · ADR-018 factor CSV delete-before-insert.

### Work-stream C — Condense & diagram

| PR    | Unit | Page                                        | Lines before → after                                            |
| ----- | ---- | ------------------------------------------- | --------------------------------------------------------------- |
| #1002 | C1   | `architecture/02-system-overview.md`        | 336 → 156 (C4 context + container + sequence)                   |
| #1005 | C2   | `backend/05-REQUEST_FLOW.md`                | 327 → 150 (sequence + auth flowchart)                           |
| #1011 | C3   | `frontend/01-overview.md`                   | 683 → 75 + 2 sub-pages (components/personas)                    |
| #1003 | C4   | `architecture/pipeline.md`                  | new (Path 1 sync UI / Path 2 async job-chain + claim_job state) |
| #1009 | C5   | `backend/07-DEVELOPER-GUIDE-PERMISSIONS.md` | 1492 → permissions/ subdir × 5 pages                            |
| #1008 | C6   | `architecture/cicd-workflows.md`            | rewrite to mirror actual `.github/workflows/`                   |

### Work-stream F — Follow-ups

| PR    | Unit | Title                                                                                                                                |
| ----- | ---- | ------------------------------------------------------------------------------------------------------------------------------------ |
| #1016 | F1   | Update agent instruction files to point at `docs/src/implementation-plans/`.                                                         |
| #1017 | F2   | Document `backend/seed_data/` as untracked SharePoint mirror (stacks on A3-redo).                                                    |
| #1018 | F3   | Integrate human-curated CSV format taxonomy + kg_co2eq override semantics; add per-file column inventory for 49 CSVs (stacks on F2). |

## Merge ordering (5-group strategy)

The 20 PRs were grouped to manage dependencies between path-affected and nav-
affected work. Same-group PRs were file-disjoint and could merge in any order.

1. **Group 1 — file-disjoint, any order:** #999 (A1), #1007 (A2), #1002 (C1), #1005 (C2), #1008 (C6), #1016 (F1).
2. **Group 2 — keystone path move:** **#1014 (B4)** — must merge before Groups 3 & 4.
3. **Group 3 — path-dependent (rebased after B4):** #1010 (B0), #1013 (B1), #1004 (B2), #1012 (B5).
4. **Group 4 — nav-dependent (B3 first, then siblings rebase onto its nav block):**
   **#1001 (B3) keystone**, then #1006 (A4), #1000 (A5), #1015 (A3-redo), #1011 (C3), #1003 (C4), #1009 (C5).
5. **Group 5 — stacked follow-ups (merge in stack order):** #1017 (F2) → #1018 (F3).

Inside Group 4, merging a sibling before B3 is non-fatal; sibling rebases pick up
B3's nav block cleanly because content does not collide.

## Discoveries surfaced (worth tracking, not in original scope)

These came up during the doc work and are flagged so they do not get lost:

1. **Spec-vs-code drifts in CSV seed formats** (from F3 review of the SharePoint
   spec vs. parser source). Inventory at
   `docs/src/backend/csv-seed-formats/inventory.md` flags each with `?` + footnote:
   - `equipments_factors.csv` — `equipment_category` is `EquipmentModuleHandler.category_field`, not stored on the factor.
   - `purchases_common_factors.csv` — `purchase_category` is `PurchaseModuleHandler.category_field`, same shape.
   - `building_rooms_data.csv` — `building_location` is silently ignored by `BuildingRoomHandlerCreate`.
   - `researchfacilities_animals_factors.csv` — `kg_co2eq_sum` is actually six per-source columns (process / building energy / rooms / purchases common / purchases additional / equipments).
2. **B4 path divergence vs. global rules.** B4 (#1014) moved plans into
   `docs/src/implementation-plans/` because that is `docs_dir`. The global rules
   file (`.github/instructions/co2-calculator-rules.md.instructions.md` lines
   45–49) mandates `docs/implementation-plans/` at repo root. Reversal is in
   progress (working-tree edit of `docs/src/implementation-plans/INDEX.md`
   rewriting it as a pointer to root); full revert needs to also update
   `gen_indexes.py:53`, `mkdocs.yml:136`, and `mkdocs.yml:187`.
3. **ADR-013 collision** — task brief expected ADR-013 to be `/me` + role-sync;
   actual ADR-013 is "Object Storage Strategy". C2 (#1005) used ADR-012/017
   instead; B1 (#1013) assigned `/me` to ADR-017.

## Follow-ups produced by this plan capture

Captured separately because they are _organizational hygiene_, not feature work:

- Move `*-copilot-feedback-*.md` artifacts out of `docs/implementation-plans/` and
  `docs/src/implementation-plans/` into `docs/code-review/`. Rationale: review
  artifacts have a different lifecycle (overwritten on re-run) than implementation
  plans (canonical, append-only). 12 files affected as of 2026-05-06.
- Update `.claude/skills/review-copilot-comments/{retrieve-copilot-pr.sh,SKILL.md}`
  to write to the new location.
- Fix mkdocs Docker build: `docs/Dockerfile` does not `COPY gen_indexes.py`, and
  the script's path resolution is brittle to the flat `/app/` layout.
