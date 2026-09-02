# Code Review: PR #2545 — data-integrity and accred-role diagnostics

**Branch:** `tools/2531-data-integrity-diagnostics`
**Date:** 2026-08-30
**Reviewer:** Claude (high-effort review, correctness-of-detection focus)
**Latest commit:** `9619cc387` — feat(scripts): add data-integrity and accred-role diagnostics (#2531)
**Diff:** 3 files, +370 / -0 — `backend/scripts/check_missing_emissions.py`,
`backend/scripts/diagnose_accred_roles.py`,
`backend/tests/performance/run_capacity_both.sh`

---

## Verdict: DO NOT SHIP as-is

One blocker (a live credential for the shared dev database, in a **public** repo),
and two detection-logic defects that make the diagnostics point at the wrong thing —
which is the failure this PR exists to prevent. The scripts are otherwise read-only,
lint-clean, and the underlying idea is right.

**Lint:** `make lint` — backend ruff/format **pass** ("All checks passed", 581 files
formatted). The frontend `eslint` step fails with `ERR_MODULE_NOT_FOUND:
eslint-plugin-vue` — that is a missing `node_modules` in this review worktree, not a
PR defect; the PR touches no frontend file. `bash -n run_capacity_both.sh` passes.
Per the brief, **no script was executed against any database.**

---

## Findings

### 1. BLOCKER — a live dev-database password is committed, in a public repo

**File:** `backend/tests/performance/run_capacity_both.sh:19`

```bash
DEV_URL='postgresql://app:LTasaXCnLE79kKPacVKrnMVKrgkNPofz@co2-dev.postgresql.dbaas.intranet.epfl.ch:5432/app'
```

- `gh repo view` reports `"isPrivate": false, "visibility": "PUBLIC"`.
- `git grep` on `origin/dev` finds this password **nowhere** — this PR introduces it.
- The one existing precedent, `backend/tests/unit/core/test_startup_checks.py:89`, uses
  the same host with the placeholder `pw`. That is the pattern to follow.

**Remediation is rotate, not delete.** The string is already in a pushed branch's
history; removing the line in a follow-up commit leaves it fully retrievable and
scrapeable. Rotate the `app` credential on `co2-dev.postgresql.dbaas.intranet.epfl.ch`,
then have the script read the DSN from the environment or from `backend/.env` (which is
gitignored and which the script already reads and rewrites anyway) rather than
hardcoding it:

```bash
DEV_URL="${PERF_DEV_DB_URL:?set PERF_DEV_DB_URL to the dev DSN}"
```

Note the contrast with `check_missing_emissions.py`, which handles this correctly —
it prints only `dsn.split("@")[-1].split("/")[0]`, so the password never reaches
stdout. Same care was owed here.

---

### 2. HIGH — `check_missing_emissions.py`: the remediation it prints will 400 out

**File:** `backend/scripts/check_missing_emissions.py:155`

```python
print(f"  POST /v1/sync/recalculate-emissions/{module_type_id}?year={year}")
```

`recalculate_emissions_for_module` (`backend/app/api/v1/data_sync.py:1976-1981`) declares
`only_stale: bool = True` and raises **400 "No data entry types require recalculation
for this module"** when nothing is stale. Whether a type is "stale" comes from
`DataIngestionRepository.get_recalculation_status_by_year`
(`backend/app/repositories/data_ingestion.py:1542`), which compares the latest
`is_current` FACTORS job id against the latest `is_current` computed DATA_ENTRIES job
id per `(module_type_id, data_entry_type_id)`. It never looks at whether
`data_entry_emissions` rows exist.

Now trace the bug this script hunts. `EMISSION_RECALC_DEDUP`
(`backend/app/tasks/_chain.py:146`) keys on
`("module_type_id", "data_entry_type_id", "year")` — **the exact grouping
`get_recalculation_status_by_year` uses.** The dedup bug means the *second* unit's
recalc child was skipped *because the first unit's job already occupies that key*.
That first job is `is_current` and newer than the factor job, so
`needs_recalculation` is **False** for precisely the scope that is missing emissions.

So the printed command returns 400 and repairs nothing. Whoever runs it concludes the
data was already fine.

**Fix:** print `?year={year}&only_stale=false`, and say in the output why the flag is
mandatory. Worth a one-line comment: `only_stale=True` is exactly the signal the dedup
bug corrupted.

---

### 3. HIGH — the "whole (module, type) group has zero emissions" signature is not specific to a skipped recalc

This is the finding that explains #2546. Three independent channels let a systemic gap
wear the dedup signature.

**(a) `emitting_types` is not year-scoped.** (`check_missing_emissions.py:45-49`)

```sql
WITH emitting_types AS (
    SELECT DISTINCT de.data_entry_type_id
    FROM data_entries de
    JOIN data_entry_emissions dee ON dee.data_entry_id = de.id
)
```

A type qualifies if it emitted *anywhere, ever*. A 2025 campaign whose factors were
never loaded therefore passes the filter on the strength of its 2024 emissions, and
every 2025 group of that type is reported as fully missing. That is a whole-year
systemic gap, not a per-`(unit, year)` dedup collision — and the query cannot tell them
apart. Scope the CTE to the same year as the group it filters (join through
`carbon_report_modules → carbon_reports` and add `cr.year` to the CTE's `DISTINCT` and
to the `IN` predicate) and this class of false positive disappears.

While checking this I confirmed the `(module, type)` grouping is redundant:
`MODULE_TYPE_TO_DATA_ENTRY_TYPES` (`backend/app/models/module_type.py:71`) partitions
data entry types 1:1 across module types, so no type spans two modules. The
cross-module false-positive I initially suspected does not exist; only the missing
year scoping does.

**(b) `--since` filters `created_at`, not the report year.** (`:72`)

The default window is `de.created_at >= 2026-06-12`. A 2025-campaign backfill *imported*
after that date is inside the window, and the headline says nothing about which years it
found. This is exactly how a 2025 gap gets read as June-2026 dedup fallout.

**(c) the output buries the year distribution.** `_print_rows` prints at most 60 rows
(`:93`) then `... and N more`, and the summary asserts causation without segmentation:

```
{entries} data entries across {len(fully)} group(s) carry no emissions and should.
Affected reports show totals that look complete but are too low.
```

With 21.9k entries across hundreds of groups, all a reader sees is a big number and a
confident sentence. **Add a year histogram before the per-group table** —
`GROUP BY cr.year` with counts of groups and entries. One extra block, and the #2546
misdiagnosis becomes impossible to make: a single-year concentration is a campaign gap,
a spread across `(unit, year)` pairs within one module is the dedup signature.

The docstring's claim that the signature "is what a skipped recalc child looks like" is
true — the converse, that only a skipped child produces it, is what the script needs and
does not have.

---

### 4. MEDIUM — `status <> 'REJECTED'` silently drops NULL-status entries

**File:** `check_missing_emissions.py:71`

```sql
AND de.status <> 'REJECTED'::dataentrystatusenum
```

`data_entries.status` is **nullable** (`alembic/versions/2026_08_20_1628-…_initial_migration.py:824-828`,
`nullable=True`; model `backend/app/models/data_entry.py:127` is
`DataEntryStatusEnum | None`). In SQL, `NULL <> 'REJECTED'` is NULL, so every
NULL-status entry is excluded from the scan. A silent false negative, in a script whose
whole job is to find silently-missing data.

Use `de.status IS DISTINCT FROM 'REJECTED'::dataentrystatusenum`.

(The enum cast itself is correct — `dataentrystatusenum` is a real PG enum with labels
`PENDING`/`VALIDATED`/`REJECTED`, despite `DataEntryStatusEnum` being an `int, Enum` in
Python.)

---

### 5. MEDIUM — PENDING is included, and nothing distinguishes "not computed yet"

Answering the question directly: **yes**, `status <> 'REJECTED'` does include PENDING —
`DataEntryStatusEnum` is `PENDING=0 / VALIDATED=1 / REJECTED=2` and only REJECTED is
excluded. That is the right default: a PENDING entry with no emissions is still a
missing computation.

But recalculation is asynchronous, so a group uploaded minutes before the run is
indistinguishable from a group whose recalc was skipped in June. The script offers no
way to separate them. Cheapest fix: add `de.status` (and `max(de.created_at)`) to the
`per_group` select and print them, so a reader can discount recent PENDING groups by eye.

---

### 6. MEDIUM — no way to rule out simulator-plan / grant reports

The query joins `carbon_reports` for `year` and `unit_id` but never looks at report
kind. Two dimensions are available and unused:

- `carbon_reports.is_grant` (`models/carbon_report.py:45`);
- report type, via `carbon_reports.carbon_project_id → carbon_projects.carbon_report_type`
  (`carbon_report_type_enum`: `Calculator` / `Simulator_Explore` / `Simulator_Plan`,
  `initial_migration.py:406-415`).

The reason to care is concrete: `MODULE_TYPE_TO_DATA_ENTRY_TYPES` contains
`planner_headcount`, `planner_purchase` and `planner_purchase_budget` — plan-side types
that plausibly resolve differently from calculator entries. I could not establish from
the source alone whether `Simulator_Plan` reports hold `data_entries` rows with no
emissions by construction, and `carbon_project_id` is nullable, so I am **not** claiming
a proven false positive here. I am claiming the script gives a reader no way to rule it
out. Add `cp.carbon_report_type` and `cr.is_grant` to the group output, or a
`--report-type` filter; it costs one LEFT JOIN.

---

### 7. LOW — the printed remediation year may not be the year the recalc keys on

The script prints `cr.year` (`carbon_reports.year`, NOT NULL). The recalc endpoint's
`year` reaches `get_recalculation_status_by_year` and is matched against
`DataIngestionJob.year`, which is the dedup key's `year`
(`_chain.py:148`). `data_entries` also carries its own nullable `year` column
(`initial_migration.py:832`). If a data entry's own year can diverge from its report's
year, the printed call targets the wrong scope. **I could not verify this without
querying data**, so flagging as something to confirm before anyone runs the output.

---

### 8. HIGH — `diagnose_accred_roles.py`: `verdict()` diverges from the real loop in the one place that matters

Compared line-by-line against `AccredRoleProvider.get_roles_by_user_id`
(`backend/app/providers/role_provider.py:562-594`).

The first three conditions match exactly, in order: `startswith("calco2.")` →
`not in VALID_ROLES` → `state != "active"`. Good.

The divergence is at the fourth and fifth. The real code:

```python
accred_unit_institutional_code = auth.get("accredunitid")
resource = auth.get("reason").get("resource")          # <- no guards
accred_unit_institutional_id = resource.get("cf") or resource.get("altname")
if not accred_unit_institutional_code: ... continue
if not accred_unit_institutional_id: ... continue
```

The script:

```python
if not auth.get("accredunitid"):
    return "DROP", "missing 'accredunitid'"
resource = (auth.get("reason") or {}).get("resource") or {}   # <- guards added
```

The `or {}` guards are the problem. In the real provider, an authorization missing
`reason` (or with `reason.resource` null) raises `AttributeError: 'NoneType' object has
no attribute 'get'` — and that extraction happens **before** the `accredunitid` guard,
so it is unavoidable. Every `except` in `get_roles_by_user_id` ends in `raise`
(`role_provider.py:632-653`), so the exception propagates: the user gets an error, **not** a wipe.

The script turns that crash into a tidy `DROP` line. A malformed payload therefore
reads as "this authorization was dropped, hypothesis C" when the real behaviour is a
different incident class entirely. That is the script lying in exactly the way the
docstring promises it will not ("kept deliberately in the same order… so a divergence
here is a divergence there").

**Fix:** mirror the real code — extract `resource` without guards, inside a
`try/except AttributeError`, and return a third status such as
`("RAISE", "reason/resource is null — the provider would raise here, not drop")`. Then
`mapped roles: 0 of N` means what the script says it means.

---

### 9. MEDIUM — `mapped roles: N of M` answers a different question than "would this user be wiped"

The script's KEEP count stops at the guards. The real loop then branches
(`role_provider.py:586-616`): `CO2_SUPERADMIN` → `GlobalScope`,
`CO2_BACKOFFICE_METIER` → `AffiliationScope`, everything else →
`_unit_or_own_scope(...)`.

The wipe is in `RoleSyncService.sync_user_units`
(`backend/app/services/role_sync_service.py:190-197`):

```python
for role in roles:
    if isinstance(role.on, (UnitScope, OwnScope)) and role.on.institutional_id:
        unit_institutional_ids.add(role.on.institutional_id)
if not unit_institutional_ids:
    await self.unit_user_service.delete_all_for_user(user.id)
```

`GlobalScope` and `AffiliationScope` contribute nothing to that set. So a user holding
only `calco2.backoffice.admin` and/or `calco2.backoffice.metier` reports a healthy
`mapped roles: 2 of 2` **and still has every unit association deleted**. For the #2531
403 wave, that is a plausible profile — and the script would clear the account.

Print the resolved scope kind per KEEP (`GlobalScope` / `AffiliationScope` /
`UnitScope` / `OwnScope`), and make the final verdict depend on whether any
`UnitScope`/`OwnScope` survived, not on the raw KEEP count. That is what
`sync_user_units` actually tests.

Also worth noting for completeness: `roles == []` is reachable by a third path the
script does not model — the provider returns `[]` early when the API is not configured
(`role_provider.py:509-515`). Same wipe, no authorizations involved.

---

### 10. LOW — the script's HTTP timeout is 2× the app's

`diagnose_accred_roles.py:73` uses `timeout=20.0`; the provider uses `timeout=10.0`
(`role_provider.py:534`). A slow Accred that times out the app will answer the script
fine, so the script cannot reproduce the transient-failure hypothesis it names
("hypothesis A or B"). Match the provider's 10s, or say in the output that a longer
timeout was used.

---

### 11. HIGH — `run_capacity_both.sh`: the restore path does not survive a midway death

**File:** `backend/tests/performance/run_capacity_both.sh:21-22, 79-80`

```bash
backup=$(mktemp)
cp "$ENV_FILE" "$backup"
...
set_db_url "$DEV_URL"          # only reached if the script runs to completion
echo "env restored to DEV DB_URL (backup: $backup)"
```

The backup is taken and then never used. There is no `trap`. Ctrl-C during phase 1, a
`make perf-load` that hangs, a closed terminal — any of these leave `backend/.env`
pointing at **localhost**, with the original in a `mktemp` file the user has to go find.
Per `project_backend_env_points_at_dev_db`, `backend/.env` is the file that decides
which database `make db-migrate` and friends talk to, so a silently-rewritten `.env` is
not a cosmetic mess.

Also, the "restore" is not a restore: it rewrites `DB_URL` to a hardcoded constant
rather than putting back the line the user had. And `set_db_url` comments out any
*additional* live `DB_URL=` line with a `# ` prefix, which is never undone — repeated
runs accumulate commented-out cruft.

**Fix — one line, covers every exit path:**

```bash
trap 'cp "$backup" "$ENV_FILE"; echo "env restored from $backup"' EXIT
```

and drop the final `set_db_url "$DEV_URL"`.

---

### 12. HIGH — no `set -e`, so a failed phase silently measures the wrong database

**File:** `run_capacity_both.sh:10`

```bash
set -uo pipefail
```

`-e` is deliberately absent (the `if start_backend …; then` guards need it absent), but
nothing guards `set_db_url`. If its inline Python raises — bad path, permissions, a
`.env` that got truncated — the failure prints a traceback and **the script continues**.
Phase 2 then starts a backend against whatever `DB_URL` was left in place and labels the
results `devdb`. The corrected numbers in #2529 came out of this script; a
silently-mislabelled ladder is the worst possible output for it.

Make `set_db_url` fatal:

```bash
set_db_url() { python3 - "$ENV_FILE" "$1" <<'PY' || { echo "FATAL: could not rewrite DB_URL"; exit 1; }
```

---

### 13. MEDIUM — the last backend is never stopped, and it holds the dev pool

`start_backend` is called twice and nothing kills the survivor. The run ends with a
2-worker uvicorn on port 8010 still attached to the **shared dev Postgres**, holding
`DB_POOL_SIZE` connections indefinitely. Given #2529 is a story about that database
running out of connections, leaving a load-test process attached to it is worth one
`kill` in the `trap`.

Related, minor: `$REPORTS` is never `mkdir -p`'d before `nohup … > "$REPORTS/…"`, and
`echo $! > …pid` records the `uv` wrapper's pid, not uvicorn's (the `pkill -f` fallback
is what actually works).

---

### 14. LOW — nits

- `PARTIAL_SQL = FULLY_MISSING_SQL.replace("WHERE missing = entries", …)`
  (`check_missing_emissions.py:80`) works, but a `--mode` parameter or an f-string
  placeholder is less likely to break silently if the predicate is ever reworded. If
  `.replace` ever misses, the script reports the same rows twice under two headings and
  nobody notices.
- `LEFT JOIN LATERAL (SELECT 1 AS data_entry_id … LIMIT 1) e ON TRUE` +
  `COUNT(*) FILTER (WHERE e.data_entry_id IS NULL)` is correct but reads as a puzzle.
  `COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM data_entry_emissions dee WHERE
  dee.data_entry_id = de.id))` says the same thing in one place.
- `datetime.strptime(args.since, "%Y-%m-%d")` (`:125`) throws a raw traceback on a typo.
- `import json` inside `main()` (`diagnose_accred_roles.py:93`) violates the
  no-inline-imports rule.
- Both scripts are correctly read-only: `check_missing_emissions` issues only `SELECT`s,
  `diagnose_accred_roles` only a `GET`. Confirmed by reading, not by running.

---

## What must change before merge

1. Rotate the dev DB credential, then remove it from the script (finding 1).
2. Add `&only_stale=false` to the printed remediation (finding 2).
3. Year-scope `emitting_types` and print a per-year histogram (finding 3).
4. `IS DISTINCT FROM 'REJECTED'` (finding 4).
5. Make `verdict()` reproduce the provider's `AttributeError` instead of guarding it
   away, and count `UnitScope`/`OwnScope` rather than raw KEEPs (findings 8, 9).
6. `trap … EXIT` restoring from `$backup`, and make `set_db_url` fatal (findings 11, 12).

Everything else is a nice-to-have.
