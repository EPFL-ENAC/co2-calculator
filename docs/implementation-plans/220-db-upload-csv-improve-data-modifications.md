# PRD — CSV Upload Feature

**CO2 Calculator · Data Ingestion Module**

|                    |                                                          |
| ------------------ | -------------------------------------------------------- |
| **Status**         | Implementation complete · Tests & validation in progress |
| **Related issues** | #368, #369, #370                                         |
| **PRs**            | PR-A: Behavior audit & error handling · PR-B: Tests      |

---

## 1. Context & Problem

The CSV Upload feature allows users to load machine-generated data (emission factors, synthetic data, and other module inputs) into the database from any module table. The backend implementation, UI, permissions, background task recalculation, and the Download CSV Template button are all in place.

Two things remain unresolved:

1. The exact runtime behavior of the upload (append-only vs. upsert vs. dedup) has not been formally verified against the spec.
2. Error handling paths (wrong format, bad encoding, wrong fields, extra columns) have not been tested end-to-end.

> **Already shipped — out of scope for these PRs:**
> Upload CSV button (UI) · Download CSV Template button · Upsert backend logic · Permissions enforcement · BackgroundTask recalculation trigger · Legacy CSV endpoint removal

---

## 2. Functional Specification

### 2.1 Upload CSV — intended behavior

The following table is the authoritative spec. PR-A must verify the implementation matches it.

| Scenario                                | Input                                            | Expected outcome                                                                                |
| --------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Valid CSV, new rows                     | All rows are new (no match in DB)                | All rows inserted. BackgroundTask triggered.                                                    |
| Valid CSV, existing machine rows        | Some rows match existing machine-flagged records | Existing machine rows updated (upsert). Human-flagged rows untouched. BackgroundTask triggered. |
| Valid CSV, human rows present           | Rows match human-flagged records                 | Human rows skipped silently. Only machine rows affected.                                        |
| Extra columns in CSV                    | CSV has columns beyond the expected schema       | Extra columns ignored. Valid columns processed normally.                                        |
| Wrong file format                       | Non-CSV file uploaded                            | Upload rejected. Error: `"Wrong CSV format or encoding"`.                                       |
| Wrong encoding                          | CSV with unsupported encoding                    | Upload rejected. Error: `"Wrong CSV format or encoding"`.                                       |
| Wrong fields / missing required columns | CSV columns do not match expected schema         | Upload rejected. Error: `"Wrong CSV format or encoding"`.                                       |
| Empty CSV                               | File has headers but no data rows                | No DB changes. No BackgroundTask. Silent success or empty-state message.                        |

### 2.2 Human vs. machine data protection

Each row in the DB carries a `source` flag (`human` | `machine`). The upload logic must:

- Never overwrite or delete rows where `source = human`.
- Only upsert rows where `source = machine`.
- The unique key used to match rows for upsert is defined per module — to be confirmed per #368, #369, #370.

### 2.3 BackgroundTask recalculation

- Triggered on every successful upload, regardless of whether rows were inserted or updated.
- Not triggered if the upload is rejected due to a formatting error.
- Not triggered if the CSV is valid but results in zero DB changes (e.g. empty file).

### 2.4 Download CSV Template

Already implemented. Out of scope for these PRs.

- Each module exposes a **Download CSV Template** button.
- The downloaded template matches the expected schema for that module's upload endpoint.
- Templates are also available on the Data OneDrive.

---

## 3. Out of Scope

- Duplicate detection / deduplication within a single CSV upload — not handled automatically, behavior TBD in a future ticket.
- Wiring Upload CSV into specific modules — tracked in #368, #369, #370.
- CSV size limits or performance constraints — not defined yet.
- UI-side format preview before submission.

---

## 4. PR Breakdown

### PR-A — Behavior audit & error handling

**Scope:** Verify and fix the backend upload behavior to match section 2.1. Ensure all error paths are handled correctly.

**Tasks:**

- Audit the current upload endpoint: confirm whether it appends, upserts, or does something else.
- Align implementation with spec (section 2.1) if divergent.
- Verify `source` flag is respected — human rows never overwritten.
- Verify error handling for: non-CSV file, wrong encoding, missing required columns.
- Verify extra columns are silently ignored.
- Confirm BackgroundTask is not triggered on rejected uploads.

**Acceptance criteria:**

- [ ] Upload behavior matches the spec table in section 2.1 for all scenarios.
- [ ] `source = human` rows are never modified by any upload.
- [ ] All error cases return `"Wrong CSV format or encoding"`.
- [ ] Extra columns in CSV are ignored without error.
- [ ] BackgroundTask fires on success, not on error.

---

### PR-B — Tests

**Scope:** Unit and integration tests covering the upload feature end-to-end. Depends on PR-A.

**Test cases to cover:**

- Happy path: valid CSV, new rows inserted, BackgroundTask triggered.
- Upsert: valid CSV with rows matching existing machine records — rows updated, not duplicated.
- Human data protection: CSV targeting human-flagged rows — those rows unchanged.
- Error: non-CSV file uploaded.
- Error: CSV with unsupported encoding.
- Error: CSV with missing required fields.
- Edge: CSV with extra/unknown columns — ignored, rest processed.
- Edge: empty CSV (headers only) — no DB change, no BackgroundTask.

**Acceptance criteria:**

- [ ] All 8 scenarios above have a corresponding test.
- [ ] Both unit (upload logic) and integration (endpoint + DB + BackgroundTask) coverage.
- [ ] CI passes on all tests.

---

## 5. Open Questions

| Question                                                                | Status                        |
| ----------------------------------------------------------------------- | ----------------------------- |
| What is the unique key per module for upsert matching?                  | To confirm per #368 #369 #370 |
| Should an empty CSV return a success or a specific empty-state message? | To confirm                    |
| Are there any CSV size or row count limits?                             | Not defined — future ticket   |

# PR-A: CSV Upload — Behavior audit & error handling

**Labels:** `backend` `data-ingestion` `needs-review`

---

## Context

The CSV upload feature is implemented. Before shipping to modules (#368 #369 #370), we need to verify that the runtime behavior matches spec and that all error paths work correctly.

## What this PR does

- Audits the upload endpoint: append-only, upsert, or something else?
- Aligns implementation with spec if divergent.
- Confirms `source = human` rows are never overwritten.
- Confirms error handling works for: wrong file type, wrong encoding, missing columns.
- Confirms extra columns are silently ignored.
- Confirms BackgroundTask is not triggered on rejected uploads.

## Acceptance criteria

- [ ] Upload behavior matches spec for all scenarios (see [PRD section 2.1](./PRD_CSV_Upload.md#21-upload-csv--intended-behavior)).
- [ ] `source = human` rows are never modified.
- [ ] All error cases return `"Wrong CSV format or encoding"`.
- [ ] Extra columns ignored without error.
- [ ] BackgroundTask fires on success only.

## Out of scope

- Tests — covered in PR-B.
- Module wiring — covered in #368 #369 #370.
- Duplicate handling within a single upload — future ticket.

# PR-B: CSV Upload — Tests (unit + integration)

**Labels:** `testing` `backend` `data-ingestion`
**Depends on:** PR-A

---

## Context

The CSV upload feature is implemented and behavior-verified (PR-A). This PR adds the full test suite.

## Test cases

- [ ] Happy path — valid CSV, new rows inserted, BackgroundTask triggered.
- [ ] Upsert — valid CSV with rows matching existing machine records, rows updated not duplicated.
- [ ] Human data protection — CSV targeting `source = human` rows, those rows unchanged.
- [ ] Error: non-CSV file uploaded.
- [ ] Error: CSV with unsupported encoding.
- [ ] Error: CSV with missing required fields.
- [ ] Edge: CSV with extra/unknown columns — ignored, rest processed normally.
- [ ] Edge: empty CSV (headers only) — no DB write, no BackgroundTask.

## Acceptance criteria

- [ ] All 8 scenarios above have a corresponding test.
- [ ] Both unit (logic) and integration (endpoint + DB + BackgroundTask) coverage.
- [ ] CI passes.

## Depends on

- PR-A must be merged first.
